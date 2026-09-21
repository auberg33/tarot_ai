import pandas as pd
import json
import time
from sqlalchemy import create_engine
import os

# =====================================================================
# 1. CONFIGURATION ET MAPPING OFFICIEL
# =====================================================================
def construire_dictionnaire_cartes():
    map_cartes = {}
    index = 0
    couleurs = [("1", "Coeur"), ("2", "Trefle"), ("3", "Carreau"), ("4", "Pique")]
    for prefixe, nom_couleur in couleurs:
        for valeur in range(1, 15):
            map_cartes[f"{prefixe}_{nom_couleur}-{valeur:02d}.gif"] = index
            index += 1
    for valeur in range(1, 22):
        map_cartes[f"5_Atout-{valeur:02d}.gif"] = index
        index += 1
    map_cartes["6_Excuse.gif"] = index
    return map_cartes

MAP_CARTES = construire_dictionnaire_cartes()

# STATUTS (Où est la carte ?)
STATUT_MA_MAIN = 0
STATUT_TAPIS = 1
STATUT_PLI_ATTAQUE = 2
STATUT_PLI_DEFENSE = 3
STATUT_CHIEN_REVELE = 4
STATUT_ECART_SECRET = 5
STATUT_INCONNU = 6

# JOUEURS RELATIFS (Qui a joué / possède la carte ?)
J_MOI = 0
J_GAUCHE = 1
J_FACE = 2
J_DROITE = 3
J_PERSONNE = 4

def position_relative(mon_id, cible_id):
    if cible_id == mon_id: return J_MOI
    if cible_id == (mon_id + 1) % 4: return J_GAUCHE
    if cible_id == (mon_id + 2) % 4: return J_FACE
    if cible_id == (mon_id + 3) % 4: return J_DROITE
    return J_PERSONNE

def determiner_gagnant_pli(pli_tuples):
    """
    Mini-moteur d'arbitrage : Détermine qui gagne le pli.
    pli_tuples: liste de (joueur_id, carte_id)
    """
    couleur_dem = -1
    meilleur_joueur = pli_tuples[0][0]
    meilleur_valeur = -1
    meilleur_est_atout = False

    # Trouver la couleur demandée (la première carte qui n'est pas l'Excuse)
    for _, id_c in pli_tuples:
        if id_c != 77:
            couleur_dem = 4 if id_c >= 56 else id_c // 14
            break

    for poseur, id_c in pli_tuples:
        if id_c == 77: continue # L'excuse ne gagne jamais le pli
        
        is_atout = (id_c >= 56)
        val = (id_c - 55) if is_atout else (id_c % 14) + 1
        coul = 4 if is_atout else id_c // 14

        if is_atout:
            if not meilleur_est_atout or val > meilleur_valeur:
                meilleur_est_atout = True
                meilleur_valeur = val
                meilleur_joueur = poseur
        elif not meilleur_est_atout and coul == couleur_dem:
            if val > meilleur_valeur:
                meilleur_valeur = val
                meilleur_joueur = poseur
                
    return meilleur_joueur

# =====================================================================
# 2. GÉNÉRATION DES PHOTOS
# =====================================================================
def generer_photo(obs, joueur_au_trait, preneur, contrat, mains_initiales, ecart_secret, chien, historique_plis, pli_en_cours, cartes_deja_jouees):
    if obs != joueur_au_trait: return None 
    
    statuts = [STATUT_INCONNU] * 78
    joueurs = [J_PERSONNE] * 78
    
    # 1. Les Plis terminés
    for pli in historique_plis:
        for poseur, c_id in pli['cartes']:
            statuts[c_id] = pli['camp_dest']
            joueurs[c_id] = position_relative(obs, poseur)
            
    # 2. Le Tapis en cours
    for poseur, c_id in pli_en_cours:
        statuts[c_id] = STATUT_TAPIS
        joueurs[c_id] = position_relative(obs, poseur)

    # 3. L'Asymétrie du Chien et de l'Écart
    if contrat in [1, 2]: # Prise ou Garde (Chien révélé)
        if obs == preneur:
            for c_id in ecart_secret: statuts[c_id] = STATUT_ECART_SECRET
        else:
            for c_id in chien:
                if statuts[c_id] == STATUT_INCONNU: 
                    statuts[c_id] = STATUT_CHIEN_REVELE
                    joueurs[c_id] = position_relative(obs, preneur)
                    
    elif contrat == 4: # Garde Sans (Chien ramassé mais secret)
        if obs == preneur:
            for c_id in chien:
                if statuts[c_id] == STATUT_INCONNU: statuts[c_id] = STATUT_ECART_SECRET

    # Garde Contre (Contrat = 5) : Le chien reste INCONNU pour tout le monde

    # 4. Ma propre main (vérité absolue)
    for c_id in mains_initiales[obs]:
        if c_id not in cartes_deja_jouees[obs] and statuts[c_id] != STATUT_ECART_SECRET:
            statuts[c_id] = STATUT_MA_MAIN
            joueurs[c_id] = J_MOI

    # 5. La Ground Truth (Où sont réellement les cartes ?)
    Y_belief = [3] * 78 # 3 = Ecart ou Inconnu
    for adv in range(4):
        if adv == obs: continue
        j_rel = position_relative(obs, adv)
        cible_idx = j_rel - 1 # 0: Gauche, 1: Face, 2: Droite
        
        for c_id in mains_initiales[adv]:
            if c_id not in cartes_deja_jouees[adv]:
                Y_belief[c_id] = cible_idx

    # Aplatissement du dictionnaire pour le CSV
    photo = {}
    photo['contrat'] = contrat
    photo['preneur_relatif'] = position_relative(obs, preneur)
    photo['joueur_actif'] = obs
    
    for i in range(78):
        photo[f'S_{i}'] = statuts[i]
        photo[f'J_{i}'] = joueurs[i]
        photo[f'Y_{i}'] = Y_belief[i]
        
    return photo

# =====================================================================
# 3. EXTRACTION BASE DE DONNÉES
# =====================================================================
print("🚀 Etape 1: Connexion à Docker...")
engine = create_engine(os.getenv('DATABASE_URL'), pool_pre_ping=True, pool_recycle=3600)

print("📊 Etape 2: Récupération des parties...")
df_ids = pd.read_sql_query("SELECT DISTINCT idPartie FROM historiquepartie", engine)
liste_ids_parties = df_ids['idPartie'].tolist()
total_parties = len(liste_ids_parties)

fichier_sortie = 'dataset_tarot_transformer.csv'
if os.path.exists(fichier_sortie): os.remove(fichier_sortie)

TAILLE_LOT = 250
temps_debut = time.time()

for i in range(0, total_parties, TAILLE_LOT):
    lot_ids = liste_ids_parties[i : i + TAILLE_LOT]
    ids_sql = ",".join(map(str, lot_ids))
    df_lot = pd.read_sql_query(f"SELECT * FROM historiquepartie WHERE idPartie IN ({ids_sql}) ORDER BY idPartie, date ASC", engine)
    
    dataset_lot = []
    
    for id_partie, df_une_partie in df_lot.groupby('idPartie'):
        preneur = -1
        contrat = 0
        chien = []
        ecart_secret = []
        mains_initiales = {0: set(), 1: set(), 2: set(), 3: set()}
        
        historique_plis = []
        cartes_deja_jouees = {0: set(), 1: set(), 2: set(), 3: set()}
        photos_partie = []
        
        for _, row in df_une_partie.iterrows():
            try: parametres = json.loads(row['parametres'])
            except: continue
            
            # PHASE 1 : DISTRIBUTION
            if row['typeHistorique'] == 1:
                preneur = int(parametres.get('preneur', -1))
                contrat = int(parametres.get('contrat', 0))
                chien = [MAP_CARTES[c] for c in parametres.get('chien', []) if c in MAP_CARTES]
                
                toutes_cartes_distribuees = set()
                for j in range(4):
                    cartes_j = [MAP_CARTES[c] for c in parametres.get(f'jeuJoueur{j}', []) if c in MAP_CARTES]
                    mains_initiales[j].update(cartes_j)
                    toutes_cartes_distribuees.update(cartes_j)
                
                # Déduction mathématique stricte de l'Écart du Preneur (les 6 cartes manquantes)
                ecart_secret = list(set(range(78)) - toutes_cartes_distribuees)

            # PHASE 2 : JEU DE LA CARTE
            elif row['typeHistorique'] == 2:
                ouvreur = int(parametres.get('main', 0))
                levees = [c for c in parametres.get('levees', []) if c in MAP_CARTES]
                pli_en_cours = []
                
                for idx, carte_nom in enumerate(levees):
                    joueur_actuel = (ouvreur + idx) % 4
                    id_carte = MAP_CARTES[carte_nom]
                    
                    # On photographie pour les 4 joueurs juste AVANT de jouer la carte
                    for obs in range(4):
                        photo = generer_photo(obs, joueur_actuel, preneur, contrat, mains_initiales, 
                                              ecart_secret, chien, historique_plis, pli_en_cours, cartes_deja_jouees)
                        if photo: photos_partie.append(photo)
                    
                    # On valide le coup
                    pli_en_cours.append((joueur_actuel, id_carte))
                    cartes_deja_jouees[joueur_actuel].add(id_carte)
                
                # Fin du pli : on résout l'arbitrage
                gagnant = determiner_gagnant_pli(pli_en_cours)
                camp_dest = STATUT_PLI_ATTAQUE if gagnant == preneur else STATUT_PLI_DEFENSE
                historique_plis.append({'cartes': pli_en_cours, 'camp_dest': camp_dest})

            # PHASE 3 : FIN DE PARTIE (Score)
            elif row['typeHistorique'] == 3:
                if preneur == -1: continue
                score_preneur = parametres.get(f'scoreManche{preneur}', 0)
                victoire_preneur = 1.0 if score_preneur >= 0 else -1.0
                
                for photo in photos_partie:
                    obs = photo['joueur_actif']
                    photo['valeur_victoire'] = victoire_preneur if obs == preneur else -victoire_preneur
                    del photo['joueur_actif'] # Plus besoin
                    dataset_lot.append(photo)
                photos_partie = []

    if dataset_lot:
        df_export = pd.DataFrame(dataset_lot)
        header = True if i == 0 else False
        df_export.to_csv(fichier_sortie, mode='a', index=False, header=header)
    
    print(f"⏳ Progression : {min(i + TAILLE_LOT, total_parties)}/{total_parties}")

print(f"\n✅ Dataset Transformer généré en {(time.time() - temps_debut) / 60:.1f} minutes.")