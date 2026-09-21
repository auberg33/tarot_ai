from engine.jeu import Carte, Jeu, Historique, InformationPartielle, MAP_CARTES_TUPLE, ANNONCES, COULEURS, Partie
from engine.joueurs import JOUEUR, IA_2
from models.tarot_former import TarotFormer
from models.tarot_value_mlp import TarotValueMLP
from collections import defaultdict
import math
import random
import copy
import torch
import torch.nn as nn
import numpy as np
import time
import torch._dynamo
import logging
import os
# Supprime les crashs intrusifs du compilateur sous Windows :
torch._dynamo.config.suppress_errors = True
logging.getLogger("torch._dynamo").setLevel(logging.ERROR)
logging.getLogger("torch._inductor").setLevel(logging.ERROR)

# --- INITIALISATION DU DEEP LEARNING ---
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class NoeudMCTSAlphaZero:

  def __init__(self, etat_jeu, parent=None, carte_jouee=None, prior=1.0):
    self.etat_jeu = etat_jeu
    self.parent = parent
    self.carte_jouee = carte_jouee
    self.enfants = {}
    self.visites = 0
    self.visites_virtuelles = (
        0  # <-- NOUVEAU : traque les descentes en cours dans le lot
    )
    self.score_preneur_cumule = 0.0
    self.prior = prior
    self.cartes_non_explorees = None

  def est_feuille(self):
    return len(self.enfants) == 0

  def est_completement_explore(self):
    return len(self.cartes_non_explorees or []) == 0

  def puct(self, c_puct=1.5):
    # Le dénominateur inclut désormais les visites virtuelles pour pénaliser temporairement le chemin
    visites_tot = self.visites + self.visites_virtuelles
    if visites_tot == 0:
      return float("inf") if self.prior > 0.5 else 1000.0 + self.prior

    moyenne_preneur = self.score_preneur_cumule / max(1, self.visites)
    parent_visites = (
        self.parent.visites + self.parent.visites_virtuelles
        if self.parent
        else 1
    )
    exploration = (
        c_puct * self.prior * math.sqrt(parent_visites) / (1 + visites_tot)
    )

    if self.parent.etat_jeu.joueur_actuel == self.parent.etat_jeu.preneur_id:
      return moyenne_preneur + exploration
    else:
      return (1.0 - moyenne_preneur) + exploration

  def meilleur_enfant(self):
    return max(self.enfants.values(), key=lambda n: n.puct())

  def ajouter_enfant(self, carte, nouvel_etat, prior):
    enfant = NoeudMCTSAlphaZero(nouvel_etat, self, carte, prior)
    self.enfants[carte] = enfant
    return enfant


class CerveauHybride:

  def __init__(
      self,
      path_belief="weights/tarot_former_belief.pth",
      path_value="weights/tarot_value_mlp.pth",
  ):
    print(f"🧠 Initialisation du Cerveau Hybride sur : {device}")

    # 1. Le Détective (Belief Network)
    self.belief_net = TarotFormer(d_model=128, nhead=4, num_layers=3).to(device)
    self.belief_net.load_state_dict(
        torch.load(path_belief, map_location=device, weights_only=True)
    )
    self.belief_net.eval()

    # 2. Le Tacticien (Value Network)
    self.value_net = TarotValueMLP(d_model=64).to(device)
    self.value_net.load_state_dict(
        torch.load(path_value, map_location=device, weights_only=True)
    )
    self.value_net.eval()

    # 3. COMPILATION PYTORCH 2.0+
    # --> LA MODIFICATION EST ICI : on ajoute "and os.name != 'nt'" pour ignorer Windows !
    if (
        hasattr(torch, "compile")
        and device.type == "cuda"
        and os.name != "nt"
    ):
      # On garde une sauvegarde propre des modèles non compilés :
      raw_belief = self.belief_net
      raw_value = self.value_net
      try:
        print("⚡ Tentative de compilation PyTorch...")
        compiled_belief = torch.compile(raw_belief, mode="reduce-overhead")
        compiled_value = torch.compile(raw_value, mode="reduce-overhead")

        # --- TEST DE PRÉCHAUFFAGE (Warmup) ---
        dummy_statuts = np.full(78, 6, dtype=np.int64)
        dummy_joueurs = np.full(78, 4, dtype=np.int64)
        dummy_pos = np.full(78, 7, dtype=np.int64)

        # On teste sur les versions compilées temporaires :
        ids_t = torch.arange(78, dtype=torch.long, device=device).unsqueeze(0)
        statuts_t = (
            torch.from_numpy(dummy_statuts)
            .to(device=device, dtype=torch.long)
            .unsqueeze(0)
        )
        joueurs_t = (
            torch.from_numpy(dummy_joueurs)
            .to(device=device, dtype=torch.long)
            .unsqueeze(0)
        )
        _ = compiled_belief(ids_t, statuts_t, joueurs_t)

        pos_t = (
            torch.from_numpy(dummy_pos)
            .to(device=device, dtype=torch.long)
            .unsqueeze(0)
        )
        _ = compiled_value(
            ids_t,
            pos_t,
            torch.tensor([0], device=device),
            torch.tensor([1], device=device),
        )

        # Si le warmup a réussi sans crasher, on valide la compilation :
        self.belief_net = compiled_belief
        self.value_net = compiled_value
        print("✅ Modèles compilés et préchauffés avec succès !")

      except Exception as e:
        # En cas d'échec (ex: Triton absent sur Windows), on restaure les modèles d'origine :
        self.belief_net = raw_belief
        self.value_net = raw_value
        print(
            "⚠️ Triton indisponible sur Windows. Bascule en mode PyTorch"
            " standard (Eager) activée."
        )
    else:
      # Si on est sous Windows (os.name == 'nt'), le script passe directement ici en silence :
      print("ℹ️ Mode PyTorch standard (Eager) actif pour Windows.")

  @torch.no_grad()
  def estimer_croyance(self, statuts, joueurs):
    """Inférence unique : retourne les probabilités (78, 4) des cartes"""
    ids_t = torch.arange(78, dtype=torch.long, device=device).unsqueeze(0)
    statuts_t = (
        torch.from_numpy(statuts)
        .to(device=device, dtype=torch.long)
        .unsqueeze(0)
    )
    joueurs_t = (
        torch.from_numpy(joueurs)
        .to(device=device, dtype=torch.long)
        .unsqueeze(0)
    )

    logits = self.belief_net(ids_t, statuts_t, joueurs_t)
    probs = torch.softmax(
        logits[0], dim=-1
    )  # [Gauche(0), Face(1), Droite(2), Écart(3)]
    return probs.cpu().numpy()

  @torch.no_grad()
  def evaluer_plateau(self, positions_absolues, preneur_rel, contrat_id):
    """Inférence rapide : estime la marge continue de victoire"""
    ids_t = torch.arange(78, dtype=torch.long, device=device).unsqueeze(0)
    pos_t = (
        torch.from_numpy(positions_absolues)
        .to(device=device, dtype=torch.long)
        .unsqueeze(0)
    )
    preneur_t = torch.tensor([preneur_rel], dtype=torch.long, device=device)
    contrat_t = torch.tensor([contrat_id], dtype=torch.long, device=device)

    valeur_norm = self.value_net(ids_t, pos_t, preneur_t, contrat_t).item()
    return valeur_norm * 50.0  # Retour en points réels de Tarot
  @torch.no_grad()
  def evaluer_batch_plateaux(
        self, batch_positions, batch_preneurs_rel, batch_contrats_id
    ):
      """Inférence GPU par lots : évalue B plateaux en un seul appel (Shape: B, 78)"""
      B = len(batch_positions)
      if B == 0:
        return []

      # 1. Préparation des tenseurs par lots (Batching)
      ids_t = (
          torch.arange(78, dtype=torch.long, device=device)
          .unsqueeze(0)
          .expand(B, -1)
      )
      pos_t = torch.from_numpy(np.array(batch_positions, dtype=np.int64)).to(
          device
      )
      preneurs_t = torch.tensor(
          batch_preneurs_rel, dtype=torch.long, device=device
      )
      contrats_t = torch.tensor(
          batch_contrats_id, dtype=torch.long, device=device
      )

      # 2. Inférence unique matricielle sur le GPU
      valeurs_norm = self.value_net(ids_t, pos_t, preneurs_t, contrats_t)

      # 3. Retour en points réels (1D array de taille B)
      return (valeurs_norm.squeeze(-1) * 50.0).cpu().numpy()

# --- ACTIVATION DU CERVEAU ---
CERVEAU_ACTIF = True
CERVEAU = CerveauHybride()

class EtatJeuMCTS:
    """Représente l'état du jeu pour MCTS avec information incomplète"""
    def __init__(self, info_partielle, distribution_cartes, historique, pli_actuel, joueur_actuel, contrat="petite"):
        self.info_partielle = info_partielle
        self.distribution_cartes = {k: v[:] for k, v in distribution_cartes.items()}
        self.historique = historique.copie_rapide() if hasattr(historique, 'copie_rapide') else copy.deepcopy(historique)
        self.pli_actuel = pli_actuel[:]
        self.joueur_actuel = joueur_actuel
        self.preneur_id = info_partielle.preneur_id
        self.contrat = contrat
        
    def est_terminal(self):
        """Vérifie si le jeu est terminé"""
        return len(self.historique.storage_plis) >= 18
    
    def obtenir_cartes_jouables(self, joueur_id):
        """Obtient les cartes que le joueur peut jouer"""
        if joueur_id == self.info_partielle.joueur_id:
            # Pour moi, j'utilise mon vrai jeu
            cartes_en_main = [self._tuple_vers_carte(t) for t in self.distribution_cartes[joueur_id]]
        else:
            # Pour les autres, j'utilise la distribution simulée
            cartes_en_main = [self._tuple_vers_carte(t) for t in self.distribution_cartes[joueur_id]]
        
        return self._determiner_cartes_legales(cartes_en_main, self.pli_actuel)
    
    def _tuple_vers_carte(self, carte_tuple):
        """Convertit un tuple (valeur, couleur) en objet Carte"""
        val, couleur = carte_tuple
        return Carte(val, couleur)
    
    def _determiner_cartes_legales(self, cartes_en_main, pli_actuel):
        """Détermine les cartes légales selon les règles du Tarot"""
        if not pli_actuel:  # Premier à jouer
            return cartes_en_main.copy()
        
        couleur_demandee = pli_actuel[0].couleur
        cartes_possibles = []
        
        if couleur_demandee == "atout":
            # Si on demande de l'atout
            atouts = [c for c in cartes_en_main if c.couleur == "atout"]
            if atouts:
                # On doit monter si possible
                plus_fort_pli = max([c.valeur for c in pli_actuel if c.couleur == "atout"])
                atouts_superieurs = [c for c in atouts if c.valeur > plus_fort_pli]
                return atouts_superieurs if atouts_superieurs else atouts
            else:
                return cartes_en_main.copy()  # Pas d'atout, on peut jouer n'importe quoi
        else:
            # Si on demande une couleur
            cartes_couleur = [c for c in cartes_en_main if c.couleur == couleur_demandee]
            if cartes_couleur:
                return cartes_couleur
            else:
                # Pas de la couleur demandée, on doit couper si possible
                atouts = [c for c in cartes_en_main if c.couleur == "atout"]
                if atouts:
                    # Vérifier si un atout a déjà été joué
                    atouts_pli = [c for c in pli_actuel if c.couleur == "atout"]
                    if atouts_pli:
                        # On doit surmonter si possible
                        plus_fort_atout = max([c.valeur for c in atouts_pli])
                        atouts_superieurs = [c for c in atouts if c.valeur > plus_fort_atout]
                        return atouts_superieurs if atouts_superieurs else atouts
                    else:
                        return atouts
                else:
                    return cartes_en_main.copy()  # Pas d'atout, on peut jouer n'importe quoi
    
    def jouer_carte(self, carte, joueur_id):
        """Joue une carte et retourne un nouvel état cloné rapidement (sans deepcopy)"""
        # Clonage superficiel ultra-rapide sans passer par deepcopy
        nouvel_etat = EtatJeuMCTS.__new__(EtatJeuMCTS)
        nouvel_etat.info_partielle = self.info_partielle
        
        # Copie rapide du dictionnaire de cartes distribuées
        nouvel_etat.distribution_cartes = {k: v[:] for k, v in self.distribution_cartes.items()}
        
        # Copie rapide de l'historique
        nouvel_etat.historique = self.historique.copie_rapide()
        
        # Copie du pli en cours
        nouvel_etat.pli_actuel = self.pli_actuel[:]
        
        nouvel_etat.joueur_actuel = self.joueur_actuel
        nouvel_etat.preneur_id = self.preneur_id
        nouvel_etat.contrat = self.contrat
        
        # Retirer la carte du jeu du joueur
        carte_tuple = (carte.valeur, carte.couleur)
        if carte_tuple in nouvel_etat.distribution_cartes[joueur_id]:
            nouvel_etat.distribution_cartes[joueur_id].remove(carte_tuple)
        
        # Ajouter la carte au pli actuel
        nouvel_etat.pli_actuel.append(carte)
        
        # Si le pli est complet (4 cartes)
        if len(nouvel_etat.pli_actuel) == 4:
            nouvel_etat.historique.ajout_pli(nouvel_etat.pli_actuel)
            nouvel_etat.pli_actuel = []
            nouvel_etat.joueur_actuel = nouvel_etat.historique.dernier_gagnant()
        else:
            nouvel_etat.joueur_actuel = (joueur_id + 1) % 4
            
        return nouvel_etat
    
    def evaluer_pour_joueur(self, joueur_id):
        if not self.est_terminal():
            return 0.5
            
        score_preneur = self.historique.score(self.preneur_id)
        nb_bouts_preneur = min(3, self.historique.nb_bout(self.preneur_id))
        
        objectifs = {3: 36, 2: 41, 1: 51, 0: 56}
        objectif = objectifs[nb_bouts_preneur]
        marge = score_preneur - objectif
        
        # --- CALCUL OFFICIEL DU SCORE DE TOURNOI ---
        coefficients = {"petite": 1, "garde": 2, "garde sans": 4, "garde contre": 6}
        facteur = coefficients.get(self.contrat, 1)
        
        epsilon = 1 if marge >= 0 else -1
        total_points = epsilon * (25 + abs(marge)) * facteur
        
        # Bonus tactique : L'IA va traquer le Petit au Bout !
        dernier_pli = self.historique.storage_plis[-1]
        if (1, "atout") in [(c.valeur, c.couleur) for c in dernier_pli]:
            if self.historique.dernier_gagnant() == self.preneur_id:
                total_points += 10 * facteur
            else:
                total_points -= 10 * facteur
                
        # Sigmoïde : Convertit les points du tournoi en une probabilité de victoire [0, 1]
        # Une division par 80.0 permet à la courbe de s'adapter aux gros scores de la FFT
        score_continu = 0.5 + (total_points / 100.0)
        score_continu = max(0.0, min(1.0, score_continu)) # On borne entre 0 et 1
        
        if joueur_id == self.preneur_id:
            return score_continu
        else:
            return 1.0 - score_continu

class IA_MCTS(JOUEUR):
    def __init__(self, jeu, id, nb_simulations=500):
        super().__init__(jeu, id)
        self.nb_simulations = nb_simulations
        self.info_partielle = None
        
    def info_preneur(self, id: int):
        """Met à jour les informations sur le preneur"""
        super().info_preneur(id)
        # Initialiser les informations partielles
        self.info_partielle = InformationPartielle(
            self.identifiant, 
            self.jeu.cartes, 
            Historique(),  # Sera mis à jour
            id
        )
        
    def joue(self, carte_jouee):
        """Retire la carte jouée de la main de l'IA et la retourne."""
        return self.jeu.supprimer(carte_jouee)
        
    def choix_carte(self, pli, historique):
        # 1. CORRECTION : Appel de la bonne méthode de la classe JOUEUR
        cartes_possibles = self.carte_jouable(pli)
        
        # Gain de temps évident : si on n'a qu'une seule carte, on la joue sans réfléchir
        if len(cartes_possibles) == 1:
            # 2. CORRECTION : Ne pas oublier self.joue() pour retirer la carte de la main !
            return self.joue(cartes_possibles[0])
            
        # Le Pruning : On retire les cartes inutiles
        # SUPPRESSION DU FILTRE : Le MCTS a besoin de toutes ses options tactiques
        cartes_filtrees = cartes_possibles
        
        # L'historique et les cartes jouées
        cartes_jouees = pli.copy()
        
        # Le MCTS Ultra-Concentré
        meilleure_carte = self.mcts_avec_determinisation(cartes_jouees, historique, cartes_filtrees)
        
        # 2. CORRECTION : Utilisation de self.joue() ici aussi
        return self.joue(meilleure_carte)

    def mcts_avec_determinisation(self, cartes_jouees, historique, cartes_possibles, temps_max=3.0):
        # === CORRECTION : SYNCHRONISATION ABSOLUE DE LA MÉMOIRE ===
        # L'IA met à jour sa vision du monde avec la stricte vérité du plateau actuel
        self.info_partielle.jeu_connu = self.jeu.cartes.copy()
        self.info_partielle.historique = historique
        self.info_partielle._mettre_a_jour_cartes_connues()
        
        # On ajoute AUSSI les cartes actuellement sur la table (pli en cours) 
        # pour éviter que le MCTS ne les redistribue à tort !
        for c in cartes_jouees:
            self.info_partielle.cartes_connues.add((c.valeur, c.couleur))
            
        # Re-génération officielle du paquet de cartes inconnues
        self.info_partielle.cartes_possibles_par_joueur = self.info_partielle._initialiser_cartes_possibles()
        # ==========================================================

        votes_cartes = defaultdict(float)
        
        probabilites_reseau, valeur_intuitive = None, 0.0
        if CERVEAU_ACTIF:
          probabilites_reseau, _ = self._interroger_cerveau(
              historique, cartes_jouees
          )

          print(f"    [Transformer-J{self.identifiant}] 🕵️ Déductions des mains adverses :")
          if probabilites_reseau:

            def get_nom_carte(idx):
              if idx == 77:
                return 0, "atout"
              elif 56 <= idx <= 76:
                return idx - 55, "atout"
              elif 0 <= idx <= 13:
                return idx + 1, "coeur"
              elif 14 <= idx <= 27:
                return idx - 13, "trefle"
              elif 28 <= idx <= 41:
                return idx - 27, "carreau"
              elif 42 <= idx <= 55:
                return idx - 41, "pique"
              return None, None

            for pos in ["gauche", "face", "droite"]:
              probs = probabilites_reseau[pos]
              top_indices = np.argsort(probs)[-3:][::-1]
              top_cartes = []
              for idx in top_indices:
                val, coul = get_nom_carte(idx)
                if val is not None and probs[idx] > 0.10:  # Filtre à 10% minimum
                  nom_carte = (
                      "Excuse"
                      if coul == "atout" and val == 0
                      else str(Carte(val, coul))
                  )
                  top_cartes.append(f"{nom_carte} ({probs[idx]*100:.0f}%)")
              if top_cartes:
                print(f"      * {pos.capitalize():<6} : {', '.join(top_cartes)}")
          print("    " + "-" * 40)
            # --- FIN DU DEBOGAGE ---

        temps_fin = time.time() + temps_max
        nb_determinisations = 0
        
        while time.time() < temps_fin:
            nb_determinisations += 1
            nb_cartes_par_joueur = self._estimer_cartes_par_joueur(historique, cartes_jouees)
            
            # Création du monde virtuel avec le Sampler V4
            distribution = self.info_partielle.generer_distribution_intelligente(nb_cartes_par_joueur, probabilites_reseau)
            
            etat_initial = EtatJeuMCTS(
                self.info_partielle, 
                distribution, 
                historique, 
                cartes_jouees, 
                self.identifiant, 
                getattr(self, 'contrat', 'petite')
            )
            
            # --- PROFONDEUR MASSIVE ---
            # Avant, on faisait 10 simulations. Maintenant, vu qu'on a élagué les cartes, 
            # on en fait 50 pour obliger le MCTS à voir sur le long terme.
            # NOUVELLE LIGNE (avec nb_simulations_max) :
            meilleure_carte_monde = self.mcts(
                etat_initial,
                cartes_possibles,
                nb_simulations_max=400,
                nb_simulations_min=160,  # (Optionnel : vous pouvez aussi le spécifier explicitement ici)
            )
            
            if meilleure_carte_monde:
                 votes_cartes[meilleure_carte_monde] += 1.0
        
        if votes_cartes:
            return max(votes_cartes.keys(), key=lambda k: votes_cartes[k])
        else:
            return random.choice(cartes_possibles)
    
    def _filtrer_cartes_utiles(self, cartes_possibles):
        if len(cartes_possibles) <= 3:
            return cartes_possibles
            
        cartes_utiles = []
        par_couleur = defaultdict(list)
        for c in cartes_possibles:
            par_couleur[c.couleur].append(c)
            
        for couleur, liste in par_couleur.items():
            liste.sort(key=lambda x: x.valeur)
            
            if couleur == "atout":
                # On garde TOUJOURS les bouts
                for c in liste:
                    if c.valeur in [0, 1, 21] and c not in cartes_utiles:
                        cartes_utiles.append(c)
                
                # On garde un éventail stratégique des autres atouts (2 petits, 2 grands)
                autres = [c for c in liste if c.valeur not in [0, 1, 21]]
                if autres:
                    if autres[0] not in cartes_utiles: cartes_utiles.append(autres[0]) 
                    if len(autres) > 1 and autres[1] not in cartes_utiles: cartes_utiles.append(autres[1]) 
                    if autres[-1] not in cartes_utiles: cartes_utiles.append(autres[-1]) 
                    if len(autres) > 2 and autres[-2] not in cartes_utiles: cartes_utiles.append(autres[-2]) 
            else:
                for c in liste:
                    if c.valeur >= 11: # On garde toutes les têtes
                        if c not in cartes_utiles: cartes_utiles.append(c)
                if liste[0] not in cartes_utiles: cartes_utiles.append(liste[0])
                if liste[-1] not in cartes_utiles: cartes_utiles.append(liste[-1])
                
        return cartes_utiles if cartes_utiles else cartes_possibles
    
    def _interroger_cerveau(self, historique, cartes_jouees, etat=None):
      """Prépare les 78 jetons pour le TarotFormer et filtre les cartes connues"""
      statuts = np.full(
          78, 6, dtype=np.int64
      )  # 6 = STATUT_INCONNU par défaut
      joueurs = np.full(
          78, 4, dtype=np.int64
      )  # 4 = J_PERSONNE par défaut

      moi = self.identifiant
      preneur = getattr(self, "preneur", -1)
      contrat = getattr(self, "contrat", "petite")

      def pos_rel(cible):
        if cible == moi:
          return 0
        if cible == (moi + 1) % 4:
          return 1
        if cible == (moi + 2) % 4:
          return 2
        if cible == (moi + 3) % 4:
          return 3
        return 4

      # 1. Plis terminés
      for pli in historique.storage_plis:
        for c in pli:
          id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
          if id_c != -1:
            statuts[id_c] = (
                2 if (pos_rel(preneur) == 0) else 3
            )  # Attaque ou Défense
            joueurs[id_c] = pos_rel(historique.dernier_gagnant())

      # 2. Tapis en cours
      id_premier = (
          historique.storage_premier_joueur[-1]
          if historique.storage_premier_joueur
          else moi
      )
      for idx, c in enumerate(cartes_jouees):
        id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
        if id_c != -1:
          statuts[id_c] = 1  # TAPIS
          joueurs[id_c] = pos_rel((id_premier + idx) % 4)

      # 3. Ma main (vérité absolue)
      for c in self.jeu.cartes:
        id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
        if id_c != -1 and statuts[id_c] not in [1, 2, 3]:
          statuts[id_c] = 0  # MA MAIN
          joueurs[id_c] = 0  # MOI

      # 4. Règles du Chien Révélé (pour la Défense)
      if contrat in ["petite", "garde"] and moi != preneur:
        for val, coul in getattr(self, "chien_revele", []):
          id_c = MAP_CARTES_TUPLE.get((val, coul), -1)
          if id_c != -1 and statuts[id_c] == 6:
            statuts[id_c] = 4  # STATUT_CHIEN_REVELE -> 100% chez le Preneur
            joueurs[id_c] = pos_rel(preneur)

      # 5. Mon propre Écart (quand je suis le Preneur)
      if moi == preneur and hasattr(self, "cartes_ecartees"):
        for c in self.cartes_ecartees:
          id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
          if id_c != -1 and statuts[id_c] == 6:
            statuts[id_c] = 5  # STATUT_ECART_SECRET
            joueurs[id_c] = 0

      # --- INFÉRENCE DU TRANSFORMER ---
      matrice_probs = CERVEAU.estimer_croyance(statuts, joueurs)

      # --- FILTRE DE RÉALITÉ ---
      # On met à 0.0 toutes les cartes qui ne sont plus dans les mains adverses !
      masque_connues = statuts != 6
      matrice_probs[masque_connues] = 0.0

      probabilites = {
          "gauche": matrice_probs[:, 0],
          "face": matrice_probs[:, 1],
          "droite": matrice_probs[:, 2],
          "ecart": matrice_probs[:, 3]
      }
      return probabilites, 0.0
    
    def _obtenir_carte_heuristique(self, etat):
        """Demande à IA_2 ce qu'elle jouerait dans cette situation précise de l'univers simulé"""
        joueur_id = etat.joueur_actuel
        
        # On reconstitue la main du joueur dans cet univers parallèle
        if joueur_id in etat.distribution_cartes:
            main_cartes = [Carte(v, c) for v, c in etat.distribution_cartes[joueur_id]]
        else:
            return None
            
        # On crée l'Oracle (IA_2)
        oracle = IA_2(main_cartes, joueur_id)
        oracle.info_preneur(etat.preneur_id)
        
        # On lui demande sa carte préférée
        try:
            carte_preferee = oracle.choix_carte(etat.pli_actuel, etat.historique)
            return carte_preferee
        except Exception:
            return None

    
        
    def encheres(self, annonces_precedentes):
        """ 
        Le MCTS délègue l'annonce à IA_2 pour ne pas se suicider en prenant 
        des contrats impossibles à tenir.
        """
        # On crée un faux joueur IA_2 temporaire avec notre main
        expert_enchere = IA_2(self.jeu.cartes, self.identifiant)
        
        # On lui demande ce qu'il ferait
        mon_annonce = expert_enchere.encheres(annonces_precedentes)
        
        # Le MCTS sauvegarde sa propre annonce (très important pour son état interne)
        self.type_annonce = mon_annonce
        return mon_annonce
    
    def _estimer_cartes_par_joueur(self, historique, cartes_jouees_pli_en_cours):
        """Calcule exactement combien de cartes il reste à chaque joueur (Anti-Crash)"""
        nb_plis_complets = len(historique.storage_plis)
        nb_cartes = {}
        
        id_premier = historique.storage_premier_joueur[-1] if historique.storage_premier_joueur else 0
        joueurs_ayant_joue_ce_pli = [(id_premier + i) % 4 for i in range(len(cartes_jouees_pli_en_cours))]
        
        for j in range(4):
            cartes_restantes = 18 - nb_plis_complets
            if j in joueurs_ayant_joue_ce_pli:
                cartes_restantes -= 1
            nb_cartes[j] = cartes_restantes
            
        return nb_cartes
    
    def mcts(
        self,
        etat_initial,
        cartes_possibles,
        nb_simulations_max=1000,
        nb_simulations_min=96,
        batch_size=32,
    ):
      """Moteur MCTS AlphaZero avec arrêt adaptatif selon la qualité du choix"""
      racine = NoeudMCTSAlphaZero(etat_initial)
      racine.cartes_non_explorees = cartes_possibles.copy()

      map_c = {"petite": 1, "garde": 2, "garde sans": 4, "garde contre": 5}
      nb_lots_max = max(1, nb_simulations_max // batch_size)
      simulations_effectuees = 0

      for _ in range(nb_lots_max):
        feuilles_lot = []
        etats_eval_lot = []

        # --- PHASE A : COLLECTE DU BATCH ---
        for _ in range(batch_size):
          noeud = racine
          noeud.visites_virtuelles += 1

          while not noeud.est_feuille() and noeud.est_completement_explore():
            noeud = noeud.meilleur_enfant()
            noeud.visites_virtuelles += 1

          if not noeud.etat_jeu.est_terminal() and noeud.cartes_non_explorees:
            carte = random.choice(noeud.cartes_non_explorees)
            noeud.cartes_non_explorees.remove(carte)
            nouvel_etat = noeud.etat_jeu.jouer_carte(
                carte, noeud.etat_jeu.joueur_actuel
            )
            
            # --- CALCUL DU PRIOR BIAISÉ PAR L'HEURISTIQUE IA_2 ---
            n_restantes = len(noeud.cartes_non_explorees) + len(noeud.enfants) + 1
            
            # On demande rapidement à IA_2 ce qu'elle jouerait ici
            carte_experte = self._obtenir_carte_heuristique(noeud.etat_jeu)
            
            if carte_experte and (carte.valeur, carte.couleur) == (carte_experte.valeur, carte_experte.couleur):
              prior = 0.50  # 50% de confiance initiale pour le coup expert
            else:
              # Le reste de la probabilité est réparti sur les autres cartes
              prior = 0.50 / max(1, n_restantes - 1)
            # -----------------------------------------------------

            noeud = noeud.ajouter_enfant(carte, nouvel_etat, prior)
            noeud.visites_virtuelles += 1
            if not nouvel_etat.est_terminal():
              noeud.cartes_non_explorees = nouvel_etat.obtenir_cartes_jouables(
                  nouvel_etat.joueur_actuel
              )

          etat_eval = noeud.etat_jeu
          if len(etat_eval.pli_actuel) > 0 and not etat_eval.est_terminal():
            etat_eval = EtatJeuMCTS(
                etat_eval.info_partielle,
                etat_eval.distribution_cartes,
                etat_eval.historique,
                etat_eval.pli_actuel,
                etat_eval.joueur_actuel,
                etat_eval.contrat,
            )
            while (
                len(etat_eval.pli_actuel) > 0 and len(etat_eval.pli_actuel) < 4
            ):
              j_actuel = etat_eval.joueur_actuel
              cartes_legales = etat_eval.obtenir_cartes_jouables(j_actuel)
              if not cartes_legales:
                break
              etat_eval = etat_eval.jouer_carte(
                  random.choice(cartes_legales), j_actuel
              )

          feuilles_lot.append(noeud)
          etats_eval_lot.append(etat_eval)

        # --- PHASE B & C : BATCH GPU ---
        batch_positions = []
        batch_preneurs_rel = []
        batch_contrats_id = []
        indices_nn = []
        scores_terminaux = {}

        for idx, (noeud, etat_eval) in enumerate(
            zip(feuilles_lot, etats_eval_lot)
        ):
          if etat_eval.est_terminal():
            scores_terminaux[idx] = etat_eval.evaluer_pour_joueur(
                etat_eval.preneur_id
            )
            continue

          moi = etat_eval.joueur_actuel
          pos = np.full(78, 7, dtype=np.int64)

          for j_id, c_list in etat_eval.distribution_cartes.items():
            if j_id == "ecart":
              continue
            rel_idx = (j_id - moi) % 4
            for val, coul in c_list:
              id_c = MAP_CARTES_TUPLE.get((val, coul), -1)
              if id_c != -1:
                pos[id_c] = rel_idx

          for idx_pli, pli in enumerate(etat_eval.historique.storage_plis):
            gagnant_pli = etat_eval.historique.storage_premier_joueur[
                idx_pli + 1
            ]
            pos_pli = 5 if gagnant_pli == etat_eval.preneur_id else 6
            for c in pli:
              id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
              if id_c != -1:
                pos[id_c] = pos_pli

          for c in etat_eval.pli_actuel:
            id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
            if id_c != -1:
              pos[id_c] = 4

          batch_positions.append(pos)
          batch_preneurs_rel.append((etat_eval.preneur_id - moi) % 4)
          batch_contrats_id.append(map_c.get(etat_eval.contrat, 1))
          indices_nn.append((idx, moi, etat_eval.preneur_id))

        resultats_gpu = CERVEAU.evaluer_batch_plateaux(
            batch_positions, batch_preneurs_rel, batch_contrats_id
        )

        # --- PHASE D : RÉTROPROPAGATION ---
        scores_finaux = [0.0] * batch_size
        for (idx, moi, preneur_id), marge_estimee in zip(
            indices_nn, resultats_gpu
        ):
          if moi != preneur_id:
            marge_estimee = -marge_estimee
          valeur_norm = 0.5 + (marge_estimee / 100.0)
          scores_finaux[idx] = max(0.0, min(1.0, valeur_norm))

        for idx, sc in scores_terminaux.items():
          scores_finaux[idx] = sc

        for noeud, score in zip(feuilles_lot, scores_finaux):
          temp = noeud
          while temp is not None:
            temp.visites_virtuelles -= 1
            temp.visites += 1
            temp.score_preneur_cumule += score
            temp = temp.parent

        simulations_effectuees += batch_size

        # # ==========================================================
        # # ⚡ CRITÈRE D'ARRÊT DYNAMIQUE : QUALITÉ ESTIMÉE DU CHOIX
        # # ==========================================================
        # if (
        #     simulations_effectuees >= nb_simulations_min
        #     and len(racine.enfants) >= 2
        # ):
        #   enfants_tries = sorted(
        #       racine.enfants.values(), key=lambda n: n.visites, reverse=True
        #   )
        #   n1 = enfants_tries[0].visites
        #   n2 = enfants_tries[1].visites

        #   # Critère 1 : Dominance absolue (N2 ne peut plus rattraper N1)
        #   if n1 - n2 > (nb_simulations_max - simulations_effectuees):
        #     break

        #   # Critère 2 : Haute confiance (Le meilleur coup concentre > 78% des visites)
        #   if (n1 / simulations_effectuees) >= 0.78:
        #     break
        # # ==========================================================

      if racine.enfants:
        return max(
            racine.enfants.values(), key=lambda n: n.visites
        ).carte_jouee
      else:
        return random.choice(cartes_possibles) if cartes_possibles else None

    def simulation_alphazero(self, etat):
      """Évaluation ultra-rapide des feuilles du MCTS par le TarotValueMLP"""
      if etat.est_terminal():
        return etat.evaluer_pour_joueur(etat.preneur_id)

      # 0. Par défaut, les cartes non attribuées (les 6 cartes de l'Écart/Chien) ont la position 7
      positions = np.full(78, 7, dtype=np.int64)

      moi = etat.joueur_actuel

      # 1. Mapping des mains simulées (0=Moi, 1=Gauche, 2=Face, 3=Droite)
      for joueur_id, cartes_tuple in etat.distribution_cartes.items():
        if joueur_id == "ecart":
          continue  # L'Écart reste à 7
        rel_idx = (joueur_id - moi) % 4
        for val, coul in cartes_tuple:
          id_c = MAP_CARTES_TUPLE.get((val, coul), -1)
          if id_c != -1:
            positions[id_c] = rel_idx

      # 2. Plis terminés : Attaque (5) vs Défense (6)
      # CORRECTION CRITIQUE : Attribution réelle selon le gagnant du pli !
      for idx_pli, pli in enumerate(etat.historique.storage_plis):
        gagnant_pli = etat.historique.storage_premier_joueur[idx_pli + 1]
        pos_pli = 5 if gagnant_pli == etat.preneur_id else 6
        for c in pli:
          id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
          if id_c != -1:
            positions[id_c] = pos_pli

      # 3. Tapis en cours (4)
      for c in etat.pli_actuel:
        id_c = MAP_CARTES_TUPLE.get((c.valeur, c.couleur), -1)
        if id_c != -1:
          positions[id_c] = 4

      # Mapping du contrat pour le réseau (1=petite, 2=garde, 4=garde sans, 5=garde contre)
      map_c = {"petite": 1, "garde": 2, "garde sans": 4, "garde contre": 5}
      contrat_id = map_c.get(etat.contrat, 1)
      preneur_rel = (etat.preneur_id - moi) % 4

      # Inférence instantanée du Value MLP (< 0.1 milliseconde)
      marge_estimee = CERVEAU.evaluer_plateau(
          positions, preneur_rel, contrat_id
      )

      # CORRECTION DU SIGNE :
      # Le MLP prédit la marge pour 'moi'. Si 'moi' est en défense,
      # on inverse le signe pour toujours renvoyer la perspective du Preneur.
      if moi != etat.preneur_id:
        marge_estimee = -marge_estimee

      # Normalisation (/ 100.0) : +50 pts -> 1.0 (Victoire), -50 pts -> 0.0 (Défaite)
      valeur_normalisee = 0.5 + (marge_estimee / 100.0)
      return max(0.0, min(1.0, valeur_normalisee))
    
    def carte_jouable(self, cartes_jouees):
        """Détermine quelles cartes le joueur peut jouer (règles du Tarot)"""
        if not cartes_jouees:  # Premier à jouer
            return self.jeu.cartes.copy()
        
        couleur_demandee = cartes_jouees[0].couleur
        cartes_possibles = []
        
        if couleur_demandee == "atout":
            # Si on demande de l'atout, on doit jouer de l'atout si on en a
            atouts = self.jeu.chercher_cartes(couleur="atout")
            if atouts:
                # On doit monter si possible
                plus_fort_pli = max([c.valeur for c in cartes_jouees if c.couleur == "atout"])
                atouts_superieurs = [c for c in atouts if c.valeur > plus_fort_pli]
                return atouts_superieurs if atouts_superieurs else atouts
            else:
                return self.jeu.cartes.copy()  # Sinon on peut jouer n'importe quoi
        else:
            # Si on demande une couleur
            cartes_couleur = self.jeu.chercher_cartes(couleur=couleur_demandee)
            if cartes_couleur:
                return cartes_couleur
            else:
                # Pas de la couleur demandée, on doit couper si possible
                atouts = self.jeu.chercher_cartes(couleur="atout")
                if atouts:
                    # Vérifier si un atout a déjà été joué
                    atouts_pli = [c for c in cartes_jouees if c.couleur == "atout"]
                    if atouts_pli:
                        # On doit surmonter si possible
                        plus_fort_atout = max([c.valeur for c in atouts_pli])
                        atouts_superieurs = [c for c in atouts if c.valeur > plus_fort_atout]
                        return atouts_superieurs if atouts_superieurs else atouts
                    else:
                        return atouts
                else:
                    return self.jeu.cartes.copy()  # Sinon on peut jouer n'importe quoi
    
    def evaluation_jeu(self): # fonction évoluée d'évaluation du jeu niveau avancé
        evaluation=0
        evaluation_speciale=0 # points spéciaux pour les gardes sans et gardes contre 

        # 10 points pour le 21
        evaluation+=10*len(self.jeu.chercher_cartes(21,"atout"))

        # 8 points pour l'excuse
        evaluation+=8*len(self.jeu.chercher_cartes(0,"atout"))

        # 0 points pour le petit avec moins de 4 atouts

        # 5 points pour le petit 5ème atout
        if len(self.jeu.chercher_cartes(couleur="atout"))==5:
            evaluation+=5*len(self.jeu.chercher_cartes(1,"atout"))

        # 7 points pour le petit 6ème atout
        if len(self.jeu.chercher_cartes(couleur="atout"))==6:
            evaluation+=7*len(self.jeu.chercher_cartes(1,"atout"))

        # 9 points pour le petit qui a plus que le 7ème atout
        if len(self.jeu.chercher_cartes(couleur="atout"))>=7:
            evaluation+=9*len(self.jeu.chercher_cartes(1,"atout"))

        # 2 points par atout (bouts compris) lorsqu'on en a plus de 4
        if len(self.jeu.chercher_cartes(couleur="atout"))>=4:
            evaluation+=2*len(self.jeu.chercher_cartes(couleur="atout"))

        # 2 points par atout majeur (entre le 16 et le 21)
        for i in range(16,22):
            evaluation+=2*len(self.jeu.chercher_cartes(i,"atout"))

        # 1 point par suite d'atouts majeurs (consécutifs)
        suite_actuelle=0
        for i in range(16,22):
            if len(self.jeu.chercher_cartes(i,"atout"))>0:
                suite_actuelle+=1
            else:
                if suite_actuelle>1:
                    evaluation+=suite_actuelle
                suite_actuelle=0
            if suite_actuelle>1:
                evaluation+=suite_actuelle

        for couleur in COULEURS:
            # 6 points pour un roi (sans dame)
            evaluation+=6*len(self.jeu.chercher_cartes(14,couleur))
            # 3 points pour une dame (sans roi)
            evaluation+=3*len(self.jeu.chercher_cartes(13,couleur))
            # 2 points par cavalier
            evaluation+=2*len(self.jeu.chercher_cartes(12,couleur))
            # 1 point par valet
            evaluation+=len(self.jeu.chercher_cartes(11,couleur))
            # 10 points par mariage (roi et dame d'une même couleur)
            if len(self.jeu.chercher_cartes(14,couleur))==1:
                if len(self.jeu.chercher_cartes(13,couleur))==1:
                    evaluation+=1 # 10-6-3=1 point supplémentaire 
        
        # Cas des longues de carte de même couleur
        compte_couleur=[len(self.jeu.chercher_cartes(couleur=i)) for i in COULEURS]
        for j in compte_couleur:
            # 9 points par longue de plus de 7 cartes
            if j>=7:
                evaluation+=9
            # 7 points par longue de plus de 6 cartes
            elif j>=6:
                evaluation+=7
            # 5 points par longue de plus de 5 cartes
            elif j>=5:
                evaluation+=5
            # 3 points spéciaux pour un singleton      
            elif j==1:
                evaluation_speciale+=3
            # 6 points spéciaux pour une coupe
            elif j==0:
                evaluation_speciale+=6 

        # choisit mon annonce en fonction
        evaluation_min=[0,40,56,71,80] # evaluation minimale pour prendre une ANNONCE (attention l'ordre est inversé)

        for i,e in enumerate(evaluation_min):
            if i<3: # passe, petite ou garde
                if evaluation>=e:
                    mon_annonce=ANNONCES[-i-1]
            else: # cas spécial pour garde sans et garde contre
                if evaluation+evaluation_speciale>=e:
                    mon_annonce=ANNONCES[-i-1]
        
        try:
            return mon_annonce
        except:
            print(evaluation)
        # return mon_annonce
    
    def choix_chien(self, chien):
        print(f"    [MCTS-J{self.identifiant}] Analyse du chien (Mode Expert Absolu)...")
        jeu_complet = self.jeu.cartes + chien.cartes
        self.jeu.cartes = jeu_complet
        self.jeu.trier()
        
        cartes_a_ecarter = []
        valides = [c for c in self.jeu.cartes if c.couleur != "atout" and c.valeur < 14]
        
        par_couleur = {coul: [c for c in valides if c.couleur == coul] for coul in ['pique', 'coeur', 'carreau', 'trefle']}
        tailles = {coul: len(par_couleur[coul]) for coul in ['pique', 'coeur', 'carreau', 'trefle']}
        couleurs_triees = sorted(['pique', 'coeur', 'carreau', 'trefle'], key=lambda x: tailles[x])
        
        # 1. Vider les couleurs courtes ENTIÈRES (Création de vraies coupes)
        for coul in couleurs_triees:
            if 0 < tailles[coul] <= 6 - len(cartes_a_ecarter):
                if not any(c.valeur == 14 and c.couleur == coul for c in self.jeu.cartes):
                    cartes_a_ecarter.extend(par_couleur[coul])
                    par_couleur[coul] = [] 
        
        # 2. Compléter en tapant dans la couleur la plus LONGUE pour ne pas créer de singletons mortels !
        if len(cartes_a_ecarter) < 6:
            couleurs_restantes = sorted([coul for coul in couleurs_triees if len(par_couleur[coul]) > 0], key=lambda x: len(par_couleur[x]), reverse=True)
            for coul in couleurs_restantes:
                cartes_dispos = sorted(par_couleur[coul], key=lambda x: x.valeur)
                while len(cartes_dispos) > 0 and len(cartes_a_ecarter) < 6:
                    cartes_a_ecarter.append(cartes_dispos.pop(0))
                if len(cartes_a_ecarter) == 6: break
                    
        # 3. Sécurité extrême
        while len(cartes_a_ecarter) < 6:
            for c in self.jeu.cartes:
                if c not in cartes_a_ecarter and c.couleur != "atout" and c.valeur != 14:
                    cartes_a_ecarter.append(c)
                    if len(cartes_a_ecarter) == 6: break
            break
            
        self.cartes_ecartees = cartes_a_ecarter
        nv_chien_tuples = [(c.valeur, c.couleur) for c in cartes_a_ecarter]
        self.jeu.cartes = [c for c in self.jeu.cartes if (c.valeur, c.couleur) not in nv_chien_tuples]
        
        if hasattr(self, 'info_partielle') and self.info_partielle:
            self.info_partielle.cartes_ecartees = self.cartes_ecartees
            # CORRECTION : Le filtre doit apprendre ce qu'on vient de ramasser !
            self.info_partielle.jeu_connu = self.jeu.cartes.copy()
            self.info_partielle.cartes_connues.clear() # On vide la mémoire corrompue
            self.info_partielle._mettre_a_jour_cartes_connues()
            self.info_partielle.cartes_possibles_par_joueur = self.info_partielle._initialiser_cartes_possibles()

        print(f"      -> Chien optimisé : {[str(c) for c in cartes_a_ecarter]}")
        return Jeu(cartes_a_ecarter)

class IA_MinMax(JOUEUR):
    def __init__(self, jeu, id, profondeur=2, nb_simu=10):
        """
        Initialise l'IA MinMax.
        - profondeur: La profondeur de la recherche dans l'arbre de jeu.
        - nb_simu: Le nombre de "mondes" aléatoires (déterminisations) à simuler.
        """
        super().__init__(jeu, id)
        self.profondeur = profondeur
        self.nb_simu = nb_simu
        # Pré-calculer le paquet complet pour l'efficacité
        deck = Jeu()
        deck.initialiser()
        self.full_deck = deck.cartes

    def choix_carte(self, cartes_jouees, historique):
        """
        Choisit la meilleure carte à jouer en utilisant l'algorithme MinMax avec déterminisation.
        C'est la fonction principale de décision de l'IA.
        """
        legal_moves = self.carte_jouable(cartes_jouees)
        
        if not legal_moves:
            # Sécurité : ne devrait pas arriver si la main n'est pas vide
            return self.jeu.cartes[0] if self.jeu.cartes else None
        if len(legal_moves) == 1:
            # Si un seul coup est possible, on le joue sans réfléchir
            return self.joue(legal_moves[0])

        move_votes = defaultdict(int)

        # Lance plusieurs simulations (déterminisations)
        for _ in range(self.nb_simu):
            # 1. Crée une "déterminisation" (un monde possible où les mains des adversaires sont connues)
            simulated_hands = self._generer_monde_aleatoire(historique, cartes_jouees)
            
            # 2. Trouve le meilleur coup pour ce monde spécifique en utilisant Minimax
            best_move_for_world, _ = self._minmax(
                simulated_hands,
                historique,
                cartes_jouees,
                self.identifiant,
                self.profondeur,
                -float('inf'),
                float('inf')
            )
            
            if best_move_for_world:
                # Ajoute un vote pour le meilleur coup trouvé dans ce monde
                move_votes[(best_move_for_world.valeur, best_move_for_world.couleur)] += 1

        if not move_votes:
            # Si, pour une raison quelconque, aucun vote n'a été enregistré, joue un coup aléatoire
            return self.joue(random.choice(legal_moves))

        # 3. Choisit le coup qui a reçu le plus de votes
        best_move_tuple = max(move_votes, key=move_votes.get)
        
        # Retrouve l'objet Carte correspondant au meilleur coup
        for carte in legal_moves:
            if (carte.valeur, carte.couleur) == best_move_tuple:
                return self.joue(carte)
        
        # Sécurité : si le coup voté n'est pas légal, joue le premier coup possible
        return self.joue(legal_moves[0])

    def _minmax(self, hands, historique, pli_en_cours, joueur_actuel, profondeur, alpha, beta):
        """
        L'algorithme MinMax récursif avec élagage alpha-bêta pour un état de jeu entièrement déterminé.
        """
        # --- Condition d'arrêt de la récursion ---
        if profondeur == 0 or len(historique.storage_plis) + (1 if len(pli_en_cours) == 4 else 0) >= 18:
            return None, self._evaluation_heuristique(historique, hands)

        # --- Gestion de la fin d'un pli ---
        if len(pli_en_cours) == 4:
            new_historique = copy.deepcopy(historique)
            new_historique.ajout_pli(pli_en_cours)
            gagnant_pli = new_historique.dernier_gagnant()
            
            # Appel récursif pour le début du prochain pli
            return self._minmax(hands, new_historique, [], gagnant_pli, profondeur - 1, alpha, beta)

        # --- Détermine si c'est au tour de l'équipe de l'IA (MAX) ou de l'adversaire (MIN) ---
        is_my_team_turn = (self.identifiant == self.preneur and joueur_actuel == self.preneur) or \
                          (self.identifiant != self.preneur and joueur_actuel != self.preneur)

        # --- Obtient les coups légaux pour le joueur actuel dans la simulation ---
        joueur_hand_sim = Jeu(hands[joueur_actuel])
        temp_player = JOUEUR(joueur_hand_sim.cartes, joueur_actuel)
        legal_moves = temp_player.carte_jouable(pli_en_cours)

        if not legal_moves:
             return None, self._evaluation_heuristique(historique, hands)

        best_move = legal_moves[0]
        
        if is_my_team_turn: # Joueur MAXIMISANT
            max_eval = -float('inf')
            for move in legal_moves:
                new_hands = {j: [c for c in h if not (c.valeur == move.valeur and c.couleur == move.couleur)] if j == joueur_actuel else h for j,h in hands.items()}
                _, current_eval = self._minmax(new_hands, historique, pli_en_cours + [move], (joueur_actuel + 1) % 4, profondeur, alpha, beta)
                
                if current_eval > max_eval:
                    max_eval = current_eval
                    best_move = move
                alpha = max(alpha, current_eval)
                if beta <= alpha:
                    break # Élagage Bêta
            return best_move, max_eval
        else: # Joueur MINIMISANT
            min_eval = float('inf')
            for move in legal_moves:
                new_hands = {j: [c for c in h if not (c.valeur == move.valeur and c.couleur == move.couleur)] if j == joueur_actuel else h for j,h in hands.items()}
                _, current_eval = self._minmax(new_hands, historique, pli_en_cours + [move], (joueur_actuel + 1) % 4, profondeur, alpha, beta)

                if current_eval < min_eval:
                    min_eval = current_eval
                    best_move = move
                beta = min(beta, current_eval)
                if beta <= alpha:
                    break # Élagage Alpha
            return best_move, min_eval

    def _evaluation_heuristique(self, historique, hands):
        """Utilise la logique de IA_2 pour évaluer la qualité d'une main simulée."""
        score_final = 0
        
        for joueur_id, hand in hands.items():
            # Évaluation basique des points de la main
            points_main = Jeu(hand).compte_points()
            
            # Évaluation avancée via IA_2
            evaluateur = IA_2(hand, joueur_id)
            score_ia2 = 0
            if evaluateur.evaluation_jeu() == "garde contre": score_ia2 += 15
            elif evaluateur.evaluation_jeu() == "garde sans": score_ia2 += 10
            elif evaluateur.evaluation_jeu() == "garde": score_ia2 += 5
            
            puissance_totale = points_main + score_ia2
            
            if joueur_id == self.preneur:
                score_final += puissance_totale
            else:
                score_final -= puissance_totale
                
        return score_final

    def _generer_monde_aleatoire(self, historique, pli_en_cours):
        """
        Génère une distribution aléatoire et cohérente des cartes inconnues pour les adversaires.
        """
        cartes_jouees = set((c.valeur, c.couleur) for pli in historique.storage_plis for c in pli)
        cartes_jouees.update((c.valeur, c.couleur) for c in pli_en_cours)
        main_ia = set((c.valeur, c.couleur) for c in self.jeu.cartes)
        
        cartes_connues = cartes_jouees.union(main_ia)
        cartes_inconnues = [c for c in self.full_deck if (c.valeur, c.couleur) not in cartes_connues]
        random.shuffle(cartes_inconnues)

        nb_cartes_main = {j: 18 - len(historique.storage_plis) for j in range(4)}
        id_premier_joueur_pli = historique.storage_premier_joueur[-1]
        for i in range(len(pli_en_cours)):
            nb_cartes_main[(id_premier_joueur_pli + i) % 4] -= 1

        simulated_hands = {j: [] for j in range(4)}
        simulated_hands[self.identifiant] = self.jeu.cartes[:]
        
        idx_carte = 0
        for j in range(4):
            if j != self.identifiant:
                nb_a_distribuer = nb_cartes_main[j]
                simulated_hands[j] = cartes_inconnues[idx_carte : idx_carte + nb_a_distribuer]
                idx_carte += nb_a_distribuer
                
        return simulated_hands
    
    def evaluation_jeu(self):
        """Évaluation de la main initiale pour choisir un contrat. Identique à l'IA_0."""
        evaluation = 0
        evaluation += len(self.jeu.chercher_cartes(couleur="atout"))
        evaluation += 2 * len(self.jeu.chercher_cartes(0, "atout") + self.jeu.chercher_cartes(1, "atout") + self.jeu.chercher_cartes(21, "atout"))
        evaluation += len(self.jeu.chercher_cartes(valeur=14, couleur=COULEURS))
        
        evaluation_min = [0, 11, 14, 18, 22]
        mon_annonce = ANNONCES[-1]
        for i, e in enumerate(evaluation_min):
            if evaluation >= e:
                mon_annonce = ANNONCES[-i-1]
        return mon_annonce

    def choix_chien(self, chien:Jeu):
        """Choix des cartes à écarter. Stratégie simple mais fonctionnelle."""
        jeu_complet = Jeu(self.jeu.cartes + chien.cartes)
        
        # Prioriser l'écart de cartes basses dans les couleurs longues où on n'a pas le roi
        cartes_candidates = []
        couleurs_triees = sorted(COULEURS, key=lambda c: len(jeu_complet.chercher_cartes(couleur=c)), reverse=True)

        for couleur in couleurs_triees:
            if not jeu_complet.chercher_cartes(valeur=14, couleur=couleur): # Si on n'a pas le roi
                cartes_couleur = jeu_complet.chercher_cartes(couleur=couleur)
                cartes_basses = sorted([c for c in cartes_couleur if c.valeur < 11], key=lambda c: c.valeur)
                cartes_candidates.extend(cartes_basses)
        
        # Compléter avec d'autres cartes si nécessaire
        if len(cartes_candidates) < 6:
            autres_cartes = [c for c in jeu_complet.cartes if c.couleur in COULEURS and c not in cartes_candidates]
            cartes_candidates.extend(sorted(autres_cartes, key=lambda c: c.valeur))
            
        nv_chien_cartes = cartes_candidates[:6]
        
        # S'assurer qu'on écarte bien 6 cartes (cas extrême où on a que des Rois/atouts)
        i = 0
        while len(nv_chien_cartes) < 6 and i < len(jeu_complet.cartes):
            c = jeu_complet.cartes[i]
            # On ne peut écarter ni Roi, ni bout
            is_roi = c.valeur == 14 and c.couleur in COULEURS
            is_bout = c.couleur == 'atout' and c.valeur in [0, 1, 21]
            if not is_roi and not is_bout and not any(c2.valeur == c.valeur and c2.couleur == c.couleur for c2 in nv_chien_cartes):
                nv_chien_cartes.append(c)
            i += 1
            
        nv_chien_tuples = set((c.valeur, c.couleur) for c in nv_chien_cartes)
        self.jeu.cartes = [c for c in jeu_complet.cartes if (c.valeur, c.couleur) not in nv_chien_tuples]

        return Jeu(nv_chien_cartes)

    def joue(self, carte_jouee):
        """Retire la carte jouée de la main de l'IA et la retourne."""
        return self.jeu.supprimer(carte_jouee)