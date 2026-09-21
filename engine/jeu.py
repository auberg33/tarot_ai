#from collections import defaultdict
import random
import copy
import numpy as np

# --- ACTIVATION DU CERVEAU ---
CERVEAU_ACTIF = True


# Dictionnaire de traduction (Format: (valeur, couleur) -> ID 0 à 77)
MAP_CARTES_TUPLE = {}
index = 0
for couleur_str, nom_couleur in [("1", "coeur"), ("2", "trefle"), ("3", "carreau"), ("4", "pique")]:
    for valeur in range(1, 15):
        MAP_CARTES_TUPLE[(valeur, nom_couleur)] = index
        index += 1
for valeur in range(1, 22):
    MAP_CARTES_TUPLE[(valeur, "atout")] = index
    index += 1
MAP_CARTES_TUPLE[(0, "atout")] = index # L'Excuse
# ---------------------------------------

# Constantes pour le jeu de tarot   
ATOUTS = list(range(22))  # Les atouts vont de 1 à 21 + le 0 est l'excuse
COULEURS = ['pique', 'coeur', 'carreau', 'trefle']
VAL_COULEUR = list(range(1, 15))  # 14 cartes par couleur
ANNONCES=["garde contre","garde sans","garde","petite","passe"] # type de contract

def ET_logique(l:list):
    if type(l)!=list:
        return ET_logique([l])
    s=True
    for e in l:
        s=s and e
    return s

def OU_logique(l:list):
    if type(l)!=list:
        return OU_logique([l])
    s=False
    for e in l:
        s=s or e
    return s

def SOMME(l:list):
    if type(l)!=list:
        return SOMME([l])
    s=0
    for e in l:
        s+=e
    return s

def MULT(l:list):
    if type(l)!=list:
        return MULT([l])
    s=1
    for e in l:
        s*=e
    return s

def factorielle(n,nb_terme=-1):
    if n<0:
        return
    if n==0 and nb_terme==1:
        return 1
    if nb_terme==-1:
        nb_terme=n
    s=1
    while n>1 and nb_terme>0:
        s*=n
        n-=1
        nb_terme-=1
    return s

def transpose(M):
    nb_ligne=len(M)
    nb_colonne=len(M[0])
    S=[[M[i][j] for i in range (nb_ligne)] for j in range (nb_colonne)]
    return S

# Représentation des cartes
class Carte:
    def __init__(self, valeur, couleur):
        self.valeur = valeur
        self.couleur = couleur
    
    def __str__(self):
        if self.couleur=="atout":
            if self.valeur==0:
                return "excuse"
            else:
                return f"Atout {self.valeur}"
        elif self.valeur<=10:
            return f"{self.valeur} de {self.couleur}"
        else:
            nom=["valet","cavalier","dame","roi"][self.valeur-11]
            return f"{nom} de {self.couleur}"

# permet de réaliser des actions/prendre des décisions sur un jeu de cartes (complet ou non)
class Jeu:
    def __init__(self,cartes=[]):
        self.cartes = cartes
    
    def affiche_cartes(self): # affiche chaque carte du jeu
        for carte in self.cartes:
            print(carte)
    
    def supprimer(self,c0:Carte):
        for carte in self.cartes:
            if carte.valeur==c0.valeur and carte.couleur==c0.couleur:
                self.cartes.remove(carte)
                return carte
    
    def initialiser(self): # met toute les cartes dans le jeu et dans l'ordre
        self.cartes = []
        # Ajouter les cartes couleurs (Piques, Coeurs, Carreaux, Trèfles)
        for couleur in COULEURS:
            for val in VAL_COULEUR:
                self.cartes.append(Carte(val, couleur))
        
        # Ajouter les atouts (de 0 à 21) 0=excuse
        for atout in ATOUTS:
            self.cartes.append(Carte(valeur=atout, couleur="atout"))
        return
    
    def melange(self):
        # mélange les cartes du jeu
        random.shuffle(self.cartes)
    
    def trier(self): # trie un jeu de carte dans l'ordre de référence
        # crée un jeu de référence pour l'ordre
        ref=Jeu()
        ref.initialiser()

        # recupère les valeurs/couleurs des cartes du jeu
        v=[]
        for carte in self.cartes:
            v.append([carte.valeur,carte.couleur])

        # classe les cartes dans le même ordre
        l=[]
        for carte in ref.cartes:
            if [carte.valeur,carte.couleur] in v:
                l.append(carte)
        self.cartes=l[:]
        return l

    def distribuer(self): # distribue les cartes en 4 paquet + 6 cartes au chien
        nb_joueurs = 4
        mains = [[] for i in range(nb_joueurs)]
        chien = []
        nb_carte=len(self.cartes)

        for i in range(6): # Le chien reçoit 6 cartes aléatoire du cartes (sauf première et dernière)
            j=random.randint(1,len(self.cartes)-1)
            chien.append(self.cartes.pop(j))
        
        for i in range(18): # Chaque joueur reçoit 18 cartes
            for j in range(nb_joueurs):
                mains[j].append(self.cartes.pop(0))
        return mains, chien
    
    def chercher_cartes(self, valeur=None, couleur=None): # cherche des cartes selon 2 filtres pouvant prendre des listes ou pas en argument
        l=[]
        for carte in self.cartes:
            if type(valeur)!=list:
                if (carte.valeur==valeur or valeur==None):
                    if type(couleur)!=list:
                        if (carte.couleur==couleur or couleur==None):
                            l.append(carte)
                    else:
                        if (carte.couleur in couleur or couleur==None):
                            l.append(carte)
            else:
                if (carte.valeur in valeur or valeur==None):
                    if type(couleur)!=list:
                        if (carte.couleur==couleur or couleur==None):
                            l.append(carte)
                    else:
                        if (carte.couleur in couleur or couleur==None):
                            l.append(carte)
        return l

    def maitre(self): # retourne la position de la carte qui gagne
        q=[]
        for carte in self.cartes:
            q.append({"valeur":carte.valeur,"couleur":carte.couleur})
        
        # S'il n'y a pas de cartes, il n'y a pas de maître.
        if not q:
            return None

        carte_joue = q[0]
        
        # Gère le cas de l'Excuse
        if (carte_joue["valeur"], carte_joue["couleur"]) == (0, "atout"):
            # FIX: Vérifie s'il y a plus d'une carte dans le pli.
            # Si l'Excuse est la seule carte, il n'y a pas encore de maître.
            # Le "maître" est techniquement le joueur de l'Excuse (qui ne gagne pas le pli).
            if len(q) < 2:
                return 0

            # S'il y a d'autres cartes, la deuxième carte définit le pli.
            carte_maitre = q[1]
            maitre = 1
        else:
            carte_maitre = q[0] # première carte jouée
            maitre = 0
        
        for k in range(1, len(self.cartes)):
            carte_joue = q[k]
            # La carte jouée n'est pas l'Excuse
            if (carte_joue["valeur"], carte_joue["couleur"]) != (0, "atout"):
                # (le joueur monte à la couleur) OU (le joueur coupe une couleur avec un atout)
                if (carte_joue["valeur"] > carte_maitre["valeur"] and carte_joue["couleur"] == carte_maitre["couleur"]) or \
                   (carte_maitre["couleur"] in COULEURS and carte_joue["couleur"] == "atout"):
                    carte_maitre = carte_joue
                    maitre = k
        return maitre

    def compte_points(self): # compte les points des cartes du jeu
        s=0
        for carte in self.cartes:
            s+=0.5
            if carte.valeur==14 and carte.couleur in COULEURS:
                s+=4
            elif carte.valeur==13 and carte.couleur in COULEURS:
                s+=3
            elif carte.valeur==12 and carte.couleur in COULEURS:
                s+=2
            elif carte.valeur==11 and carte.couleur in COULEURS:
                s+=1
            elif carte.valeur in [1,21] and carte.couleur=='atout':
                s+=4
        return s
    
    def complementaire(self):
        # référence
        j=Jeu()
        j.initialiser()
        # liste des cartes qui sont dans liste_cartes_jouees
        s=[(carte.valeur,carte.couleur) for carte in self.cartes]
        # liste des cartes qui ne sont pas dans liste_cartes_jouees
        self.cartes=[]
        for carte in j.cartes:
            if (carte.valeur,carte.couleur) not in s:
                self.cartes.append(Carte(carte.valeur,carte.couleur))
        return self
    
    def carte_max(self,couleur=None):
        if couleur==None:
            l=[carte.valeur for carte in self.cartes]
            l=[carte for carte in self.cartes if carte.valeur==max(l)]
        else:
            l=[carte.valeur for carte in self.cartes if carte.couleur==couleur]
            l=[carte for carte in self.cartes if carte.couleur==couleur and carte.valeur==max(l)]
        if len(l)>0:
            return l[0]
        else:
            return None
            
    def carte_min(self,couleur=None):
        if couleur==None:
            l=[carte.valeur for carte in self.cartes]
            l=[carte for carte in self.cartes if carte.valeur==min(l)]
        else:
            l=[carte.valeur for carte in self.cartes if carte.couleur==couleur]
            l=[carte for carte in self.cartes if carte.couleur==couleur and carte.valeur==min(l)]
        if len(l)>0:
            return l[0]
        else:
            return None

class Historique:
    def __init__(self,premier_joueur=0):
        # stock l'ensemble des cartes jouées lors d'une partie sous la forme
        # d'une liste de liste des plis [[carte0,carte1,carte2,carte3],...]
        # l'ordre des cartes correspond à l'ordre des identifiants des joueurs
        self.storage_plis=[] # pli
        self.storage_premier_joueur=[premier_joueur] #identifiants
        self.storage_pli_en_cours=[] # pli en cours
    
    def copie_rapide(self):
        nv = Historique(self.storage_premier_joueur[0])
        nv.storage_plis = [pli[:] for pli in self.storage_plis]
        nv.storage_premier_joueur = self.storage_premier_joueur[:]
        nv.storage_pli_en_cours = self.storage_pli_en_cours[:]
        return nv

    def pli_en_cours(self,cartes:list): # liste des cartes du pli en cours dans l'ordre joué
        self.storage_pli_en_cours=[]
        for j in range(len(cartes)):
            self.storage_pli_en_cours.append(cartes[j]) # pli en cours (seulement joué en partie), dans ordre de jeu

    def ajout_pli(self,cartes:list): #liste des cartes dans l'ordre jouée
        # détermine le gagnant du pli
        p=Jeu(cartes).maitre() # position du maitre
        i=self.storage_premier_joueur[-1] # celui qui a commencé
        k=(i+p)%4 #joueur maitre
        self.storage_premier_joueur.append(k)

        # ajoute les cartes au stockage (0 -> carte du joueur 0)
        l=[cartes[0-i],cartes[1-i],cartes[2-i],cartes[3-i]]
        self.storage_plis.append(l)
    
    def gagnant_tour(self,n:int): # n étant entre 0 et le nb de tour joué
        if 0<=n and n<=len(self.storage_plis)-1:
            return self.storage_premier_joueur[n+1]
        else:
            return
    
    def pli_joue(self,n:int): # retourne un pli dans l'ordre des cartes jouées
        if 0<=n and n<=len(self.storage_plis)-1:
            l=[(self.storage_premier_joueur[n]+i)%4 for i in range (4)]
            l=[self.storage_plis[n][l0] for l0 in l]
            return l
        else:
            return
    
    def pli_trier(self,n:int): # retourne un pli dans l'ordre des identifiants des joueurs
        if 0<=n and n<=len(self.storage_plis)-1:
            l=[self.storage_plis[n][j] for j in range (4)]
            return l
        else:
            return
    
    def dernier_gagnant(self): # joueur ayant gagné le dernier pli
        return self.storage_premier_joueur[-1]

    def score(self, joueur: int):
      s = 0
      for i, pli in enumerate(self.storage_plis):
        # 1. Gestion de l'Excuse (reste à celui qui l'a jouée : joueur == j)
        if (0, "atout") in [(c.valeur, c.couleur) for c in pli]:
          j = [(c.valeur, c.couleur) for c in pli].index((0, "atout"))
          if joueur == j:
            s += 4

        # 2. Points normaux des plis remportés
        if joueur == self.storage_premier_joueur[i + 1]:
          s += Jeu(pli).compte_points()
      return s

    def nb_bout(self, joueur: int):
      s = 0
      for i, pli in enumerate(self.storage_plis):
        # 1. L'Excuse reste à celui qui l'a jouée (joueur == j)
        if (0, "atout") in [(c.valeur, c.couleur) for c in pli]:
          j = [(c.valeur, c.couleur) for c in pli].index((0, "atout"))
          if joueur == j:
            s += 1

        # 2. Le Petit (1) et le 21 vont à celui qui remporte le pli
        if joueur == self.storage_premier_joueur[i + 1]:
          if (1, "atout") in [(c.valeur, c.couleur) for c in pli]:
            s += 1
          if (21, "atout") in [(c.valeur, c.couleur) for c in pli]:
            s += 1
      return s
    
    def nombre_plis_remportes(self,joueur:int): # donne le nombre de plis remportés par un joueur
        n=0
        for i,pli in enumerate(self.storage_plis):
            if joueur==self.storage_premier_joueur[i+1]: # le joueur commence au tour i+1
                n+=1 # alors, le joueur a gagné le pli i
        return n

    def chelem(self,joueur:int): # détermine si un joueur a gagné un chelem
        if self.nombre_plis_remportes(joueur)==len(self.storage_plis):
            return True # le preneur a gagné toutes les plis
        elif self.nombre_plis_remportes(joueur)==len(self.storage_plis)-1:
            pli=self.storage_plis[-1]
            i=len(self.storage_plis)
            if (0,"atout") in [(carte.valeur,carte.couleur) for carte in pli]:
                j=[(carte.valeur,carte.couleur) for carte in pli].index((0,"atout"))
                if joueur==(j+self.gagnant_tour(i))%4: # le joueur a l'excuse
                    return True # le preneur a gagné toutes les plis, sauf celle de l'excuse qu'il possédait

    def petit_au_bout(self,joueur:int):
        pli=self.storage_plis[-1]
        if self.chelem(joueur):
            if (0,"atout") in [(carte.valeur,carte.couleur) for carte in pli]:
                j=[(carte.valeur,carte.couleur) for carte in pli].index((0,"atout"))
                i=len(self.storage_plis)
                gagnant_relatif = self.gagnant_tour(i)
                if gagnant_relatif is not None and joueur == (j + gagnant_relatif) % 4: # LE CORRECTIF
                    if (1,"atout") in [(carte.valeur,carte.couleur) for carte in pli]:
                        pli=self.storage_plis[-2]
        i=len(self.storage_plis)
        if (1,"atout") in [(carte.valeur,carte.couleur) for carte in pli]:
            j=[(carte.valeur,carte.couleur) for carte in pli].index((1,"atout"))
            gagnant_relatif = self.gagnant_tour(i)
            if gagnant_relatif is not None and joueur == (j + gagnant_relatif) % 4: # LE CORRECTIF
                return True
        return False


    def __str__(self):
        s=""
        for index,pli in enumerate(self.storage_plis):
            s+=f"{index} : {pli[0]} / {pli[1]} / {pli[2]} / {pli[3]}\n"
        return s

    def affiche_tour(self,n:int):
        if 0<=n and n<=len(self.storage_plis)-1:
            s=f"Tour n{len(self.storage_plis)-1+1}"
            p=self.storage_premier_joueur[n]
            for i in range (len(self.storage_plis[n])):
                joueur=(p+i)%4
                s+=f"\nJ{joueur+1} : {self.storage_plis[n][joueur]}"
            print(s)
            return
        else:
            return

class Partie:
    def __init__(self):
        self.liste_joueurs = [] #liste de joueur
        self.chien = None #Jeu
        self.preneur = None #joueur : IA_0/IA_1/IA_2 ou joueur
        self.type_annonce = None #élement de la liste ANNONCES
        self.historique = None #Historique
        self.liste_poignees=[] # liste des poignees des joueurs
        self.petit_au_bout_preneur=None # joueur ayant mis le petit au bout (s'il existe)
        self.petit_au_bout_defenseur=None # joueur ayant mis le petit au bout (s'il existe)
        self.chelem_preneur=None # chelem realisé par le preneur
        self.chelem_defenseur=None # chelem réalisé par le défenseur
        self.chelem_annonce=None # joueur ayant annoncé un chelem (s'il existe)
        self.id=None

    def score_manche(self,marge): # calcul des scores à la fin d'une manche
        coefficients=[6,4,2,1,0] # facteurs multiplicatifs des différentes prises
        prime_poignee=0 # prime de poignée
        prime_petit=0 # prime du petit au bout
        epsilon=0 # facteur de gain ou de perte
        prime_chelem=0 # prime de chelem
        # for i in range(len(coefficients)):
        #     if self.type_annonce==ANNONCES[i]:
        #         facteur=coefficients[i]

        for index,annonce in enumerate(ANNONCES):
            if self.type_annonce==annonce:
                facteur=coefficients[index]

        if marge>=0:
            epsilon=1
        elif marge<0:
            epsilon=-1
        for poignee in self.liste_poignees:
            if poignee==3: # Triple poignée avec 15 atouts
                prime_poignee+=40
            elif poignee==2: # Double poignée avec 13 atouts
                prime_poignee+=30
            elif poignee==1: # Simple poignée avec 10 atouts
                prime_poignee+=20
        if self.petit_au_bout_preneur:
            prime_petit=10
        elif self.petit_au_bout_defenseur:
            prime_petit=-10
        if self.chelem_annonce:
            if self.chelem_preneur:
                prime_chelem=400
            else:
                prime_chelem=-200
        elif not self.chelem_annonce:
            if self.chelem_preneur:
                prime_chelem=200
            elif self.chelem_defenseur:
                prime_chelem=-200
        total=epsilon*((25+abs(marge))*facteur+prime_poignee+prime_chelem)+prime_petit*facteur
        score_preneur=3*total
        score_defenseur=-total
        return score_preneur,score_defenseur
    
    def partie(self, nb_tour=18, dif=[2,2,2,2], nb_donne=1, donneur=0):
        ## 1/distribution des cartes
        premier_joueur = (donneur + 1) % 4
        print("\n" + "="*20 + f" NOUVELLE PARTIE (Donne n°{nb_donne}) " + "="*20)
        print(f"Donneur : J{donneur} | Le premier à parler et jouer sera J{premier_joueur}")
        self.distribution(dif, donneur)
        print("-" * 50)

        ## 2/Mise en place des annonces et chien
        print("Début de la phase d'annonces...")
        r = self.annonces(donneur)
        if not r:
            print("Tous les joueurs ont passé. La donne est annulée.")
            return (0, True, None)
        print("-" * 50)

        ## 3/tours de jeu
        for tour in range(nb_tour):
            self.tour() 
            gagnant = self.historique.dernier_gagnant()
            print(f"  Le pli est remporté par J{gagnant}.")

        ## 4/comptage des points
        print("\n" + "="*20 + " FIN DE LA MANCHE " + "="*20)
        p = self.liste_joueurs.index(self.preneur)
        self.nb_point_preneur = self.historique.score(p)
        self.nb_point_defense = 0
        for j in range(4):
            if j != p:
                self.nb_point_defense += self.historique.score(j)
        
        if self.type_annonce in ANNONCES[0:2]: # garde sans et garde contre
            self.nb_point_defense += self.chien.compte_points()
        else: # classique
            self.nb_point_preneur += self.chien.compte_points()

        print(f"  Points Preneur (J{self.preneur.identifiant}): {self.nb_point_preneur:.1f}")
        print(f"  Points Défense: {self.nb_point_defense:.1f}")

        ## 5/décision du gagnant
        nb_bouts_preneur = min(3, self.historique.nb_bout(p)) # LE CORRECTIF EST LE min(3, ...)
        liste_score_min = [56, 51, 41, 36]
        objectif = liste_score_min[nb_bouts_preneur]
        print(f"  Objectif du preneur ({nb_bouts_preneur} bout(s)): {objectif} points")
        marge = self.nb_point_preneur - objectif
        print(f"  Marge brute: {marge:.1f} points")

        self.primes() # Met à jour les primes avant de calculer le score officiel

        if marge >= 0:
            print(">>> VICTOIRE DU PRENEUR <<<")
        else:
            print(">>> VICTOIRE DE LA DÉFENSE <<<")
            
        return (marge, False, self.preneur.identifiant)
    
    def distribution(self, difficultes=[1,1,2,2], donneur=0):
        from engine.joueurs import IA_0, IA_1, IA_2
        from engine.mcts import IA_MCTS, IA_MinMax
        p = Jeu()
        p.initialiser()
        p.melange()
        main, chien = p.distribuer()
        self.chien = Jeu(chien)
        for index, jeu in enumerate(main):
            if difficultes[index] == 0: joueur = IA_0(jeu, index)
            elif difficultes[index] == 1: joueur = IA_1(jeu, index)
            elif difficultes[index] == 2: joueur = IA_2(jeu, index)
            elif difficultes[index] == "MCTS": joueur = IA_MCTS(jeu, index)
            elif difficultes[index] == "MinMax": joueur = IA_MinMax(jeu, index)
            
            self.liste_joueurs.append(joueur)
            print(f"  J{index}: {type(joueur).__name__}")
            
        # Le premier joueur est celui à droite du donneur
        self.historique = Historique(premier_joueur=(donneur + 1) % 4)

    def annonces(self, donneur=0): 
        annonces_faites = []
        # Rotation de l'ordre de parole
        joueurs_ordre = [(donneur + 1 + i) % 4 for i in range(4)]
        
        for id_joueur in joueurs_ordre:
            joueur = self.liste_joueurs[id_joueur]
            annonce = joueur.encheres(annonces_faites)
            annonces_faites.append(annonce)
            print(f"  Annonce J{joueur.identifiant}: {annonce}")
        
        if all(a == ANNONCES[-1] for a in annonces_faites):
            return False
        
        h = [ANNONCES.index(a) for a in annonces_faites]
        idx_best = h.index(min(h))
        self.type_annonce = annonces_faites[idx_best]
        p = joueurs_ordre[idx_best] # ID du vrai preneur
        
        print(f"\n>>> Le preneur est J{p} avec un contrat de '{self.type_annonce}'.")
        self.preneur = self.liste_joueurs[p]
        for joueur in self.liste_joueurs:
            joueur.info_preneur(p)
            joueur.contrat = self.type_annonce

        if self.type_annonce not in ANNONCES[0:2]:
          print(f"  Chien initial: {[str(c) for c in self.chien.cartes]}")
          for j in self.liste_joueurs:
            if hasattr(j, "memoriser_chien"):
              j.memoriser_chien(self.chien.cartes)
          self.chien = self.preneur.choix_chien(self.chien)
          print(
              f"  Chien final (écarté par J{p}):"
              f" {[str(c) for c in self.chien.cartes]}"
          )
        return True

    def primes(self): # met à jour les différentes primes
        for joueur in self.liste_joueurs:
            self.liste_poignees.append(joueur.poignees())
            if self.historique.petit_au_bout(joueur):
                if joueur==self.preneur:
                    self.petit_au_bout_preneur=True
                else:
                    self.petit_au_bout_defenseur=True
        if self.nb_point_defense==0: # aucun point pour la défense
            self.chelem_preneur=True
        elif self.nb_point_preneur==0: # aucun point pour le preneur
            self.chelem_defenseur=True

    def tour(self): # joue un tour
        pli=[]
        print(f"\n--- Tour {len(self.historique.storage_plis) + 1} ---")
        premier_joueur = self.historique.storage_premier_joueur[-1]
        for i in range (4):
            p=(premier_joueur+i)%4 
            print(f"  Tour de J{p}:")
            carte_jouee=self.liste_joueurs[p].choix_carte(pli,self.historique)
            print(f"    -> Joue: {carte_jouee}") # Affichage de la carte jouée
            pli.append(carte_jouee) 
            self.historique.pli_en_cours(pli)
        self.historique.ajout_pli(pli)
    
    def affiche_cartes_joueurs(self):
        print("-"*50)
        for j in self.liste_joueurs:
            print("Jeu du joueur")
            j.jeu.affiche_cartes()
            print("-"*50)
        return


class InformationPartielle:
    """Gère les informations partielles dans le jeu de Tarot"""
    def __init__(self, joueur_id, jeu_joueur, historique, preneur_id=None, cartes_ecartees=None):
        self.joueur_id = joueur_id
        self.jeu_connu = jeu_joueur.copy()
        self.historique = historique
        self.preneur_id = preneur_id
        self.cartes_ecartees = cartes_ecartees or []
        
        # Cartes connues (jouées + mon jeu + écart)
        self.cartes_connues = set()
        self._mettre_a_jour_cartes_connues()
        
        # Cartes restantes possibles pour chaque joueur
        self.cartes_possibles_par_joueur = self._initialiser_cartes_possibles()

    def _mettre_a_jour_cartes_connues(self):
        """Met à jour les cartes connues (mon jeu + cartes jouées + écart)"""
        self.cartes_connues.clear() # <--- CORRECTION : On vide l'ancienne mémoire
        for carte in self.jeu_connu:
            self.cartes_connues.add((carte.valeur, carte.couleur))
        for pli in self.historique.storage_plis:
            for carte in pli:
                self.cartes_connues.add((carte.valeur, carte.couleur))
        for carte in self.cartes_ecartees: # <-- Intégration de l'Écart
            self.cartes_connues.add((carte.valeur, carte.couleur))
    
    def _initialiser_cartes_possibles(self):
        """Initialise les cartes possibles pour chaque joueur"""
        # Créer le jeu complet
        jeu_complet = []
        COULEURS = ["pique", "coeur", "carreau", "trefle"]
        VAL_COULEUR = list(range(1, 15))
        ATOUTS = list(range(0, 22))
        
        for couleur in COULEURS:
            for val in VAL_COULEUR:
                jeu_complet.append((val, couleur))
        for atout in ATOUTS:
            jeu_complet.append((atout, "atout"))
        
        # Cartes non connues (pas dans mon jeu, pas jouées)
        cartes_inconnues = []
        for carte_tuple in jeu_complet:
            if carte_tuple not in self.cartes_connues and not self._est_dans_mon_jeu(carte_tuple):
                cartes_inconnues.append(carte_tuple)
        
        return cartes_inconnues
    
    def _est_dans_mon_jeu(self, carte_tuple):
        """Vérifie si une carte est dans mon jeu"""
        val, couleur = carte_tuple
        for carte in self.jeu_connu:
            if carte.valeur == val and carte.couleur == couleur:
                return True
        return False
    
    def _position_relative(self, j_cible):
        if j_cible == (self.joueur_id + 1) % 4: return 'gauche'
        if j_cible == (self.joueur_id + 2) % 4: return 'face'
        if j_cible == (self.joueur_id + 3) % 4: return 'droite'
        return 'moi'

    def generer_distribution_intelligente(
        self, nb_cartes_par_joueur, probabilites_reseau=None
    ):
      """Distribue les cartes inconnues selon les probabilités dictées par le Transformer"""
      cartes_a_distribuer = self.cartes_possibles_par_joueur.copy()
      random.shuffle(cartes_a_distribuer)

      distribution = {i: [] for i in range(4)}
      distribution[self.joueur_id] = [
          (c.valeur, c.couleur) for c in self.jeu_connu
      ]

      capacites = {
          j: nb_cartes_par_joueur[j]
          for j in range(4)
          if j != self.joueur_id
      }

      # Le paradoxe de l'Écart : si on n'est pas le preneur, il y a 6 cartes secrètes dans l'univers
      if self.joueur_id != self.preneur_id:
        capacites["ecart"] = 6

      # Sécurité : Si le cerveau est inactif, on distribue au hasard
      if probabilites_reseau is None:
        idx = 0
        for k in capacites.keys():
          for _ in range(capacites[k]):
            if idx < len(cartes_a_distribuer):
              if k != "ecart":
                distribution[k].append(cartes_a_distribuer[idx])
              idx += 1
        return distribution

      # --- DISTRIBUTION INTELLIGENTE (CORRIGÉE) ---
      T = 1.3  # Température : adoucit les probabilités pour maintenir une diversité dans le MCTS

      for carte in cartes_a_distribuer:
        id_carte = MAP_CARTES_TUPLE.get(carte, -1)

        # 1. Ne garder que les cibles (joueurs ou Écart) qui ont encore de la place
        joueurs_valides = [
            k for k, cap in capacites.items() if cap > 0
        ]
        if not joueurs_valides:
          break  # Toutes les mains sont pleines

        # 2. Construire le dictionnaire des poids pour CETTE carte
        poids = {}
        for k in joueurs_valides:
          if id_carte != -1:
            # CORRECTION CRITIQUE 1 : L'Écart utilise sa propre classe (indice 3 du Transformer)
            if k == "ecart":
              poids[k] = probabilites_reseau["ecart"][id_carte]
            else:
              pos = self._position_relative(k)
              poids[k] = probabilites_reseau[pos][id_carte]
          else:
            poids[k] = 1.0

        # 3. CORRECTION CRITIQUE 2 : Application unique et propre de la Température T=1.3
        somme_poids = sum(poids.values())
        if somme_poids > 0:
          # Équation Softmax avec température : P_i = (w_i ^ (1/T)) / sum(w_k ^ (1/T))
          probs_temp = [
              (max(1e-9, poids[j]) / somme_poids) ** (1.0 / T)
              for j in joueurs_valides
          ]
          somme_probs = sum(probs_temp)
          probs = [p / somme_probs for p in probs_temp]

          joueur_choisi = random.choices(
              joueurs_valides, weights=probs, k=1
          )[0]
        else:
          joueur_choisi = random.choice(joueurs_valides)

        # 4. Affectation de la carte dans l'univers simulé
        if joueur_choisi != "ecart":
          distribution[joueur_choisi].append(carte)
        capacites[joueur_choisi] -= 1

      return distribution
    
    def mettre_a_jour_avec_pli(self, pli):
        """Met à jour les informations après un pli joué"""
        for carte in pli:
            self.cartes_connues.add((carte.valeur, carte.couleur))
            # Retirer des cartes possibles
            if (carte.valeur, carte.couleur) in self.cartes_possibles_par_joueur:
                self.cartes_possibles_par_joueur.remove((carte.valeur, carte.couleur))
