from engine.jeu import Partie
from engine.joueurs import IA_2,IA_1,IA_0
from engine.mcts import IA_MCTS
import sys
import os
import io
import math
import random

def evaluer_modeles(nb_parties=100, matchup=["MCTS", 2, 2, 2]):

    print("\n" + "="*60)
    print(f"🚀 TOURNOI OFFICIEL PROFILER : {nb_parties} parties.")
    print(f"Matchup : J0={matchup[0]} | J1={matchup[1]} | J2={matchup[2]} | J3={matchup[3]}")
    print("Calcul en cours... Les 'Pires Parties' seront sauvegardées dans un fichier texte.")
    print("="*60)

    stats = {
        "parties_jouees": 0,
        "parties_annulees": 0,
        "score_tournoi": {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0},
        "attaque": {i: {"prises": 0, "gagnees": 0, "chutes": 0, "marge_moyenne": 0.0, "bouts_moyens": 0.0, "chutes_graves": 0} for i in range(4)},
        "defense": {i: {"parties": 0, "marge_moyenne_subie": 0.0} for i in range(4)}
    }

    # Préparation du fichier d'autopsie
    fichier_log = "pires_parties_mcts.txt"
    with open(fichier_log, "w", encoding="utf-8") as f:
        f.write("=== ARCHIVE DES PIRES PARTIES DU MCTS ===\n")
        f.write("Ici sont stockées les parties où le MCTS a pris un contrat avec un bon jeu mais s'est fait écraser.\n\n")

    original_stdout = sys.stdout

    pourcent_en_cours = 0

    try:
        for i in range(nb_parties):
            if math.floor(100*i/nb_parties) > pourcent_en_cours:
                pourcent_en_cours+=1
                print(pourcent_en_cours," %")

            donneur_tournant = i % 4
            partie = Partie()
            
            # --- LE MAGNÉTOPHONE ---
            # On détourne les 'print' de la console vers un espace mémoire (tampon)
            tampon = io.StringIO()
            sys.stdout = tampon
            
            try:
                resultat = partie.partie(nb_tour=18, dif=matchup, nb_donne=i+1, donneur=donneur_tournant)
            except Exception as e:
                # Si le jeu crash, on remet l'affichage et on l'affiche
                sys.stdout = original_stdout
                print(f"⚠️ Erreur lors de la donne {i+1}: {e}")
                sys.stdout = tampon
                continue

            # On remet l'affichage à la normale après la partie
            sys.stdout = original_stdout

            if not resultat or len(resultat) != 3: continue
            marge, annulee, preneur_id = resultat

            if annulee:
                stats["parties_annulees"] += 1
                continue

            stats["parties_jouees"] += 1

            # --- LE FILTRE D'AUTOPSIE ---
            # Si le MCTS (J0) est preneur et qu'il subit une chute grave (<= -15 pts)
            if preneur_id == 0 and marge <= -15:
                with open(fichier_log, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*20} DONNE {i+1} : CHUTE GRAVE (Marge: {marge:+.1f}) {'='*20}\n")
                    f.write(tampon.getvalue()) # On écrit tout l'historique de la partie !
                    f.write("\n\n")

            # --- Mise à jour des Stats Classiques ---
            stats["attaque"][preneur_id]["prises"] += 1
            if marge >= 0:
                stats["attaque"][preneur_id]["gagnees"] += 1
            else:
                stats["attaque"][preneur_id]["chutes"] += 1
                if marge <= -20: 
                    stats["attaque"][preneur_id]["chutes_graves"] += 1
            
            stats["attaque"][preneur_id]["bouts_moyens"] += partie.historique.nb_bout(preneur_id)

            score_preneur_tournoi, score_defenseur_tournoi = partie.score_manche(marge)
            
            for j in range(4):
                if j == preneur_id:
                    stats["score_tournoi"][j] += score_preneur_tournoi
                    stats["attaque"][j]["marge_moyenne"] += marge
                else:
                    stats["score_tournoi"][j] += score_defenseur_tournoi
                    stats["defense"][j]["parties"] += 1
                    stats["defense"][j]["marge_moyenne_subie"] += marge 
                    
            # On vide le magnétophone pour la partie suivante
            tampon.close()

    finally:
        sys.stdout = original_stdout

    # --- FINALISATION ET AFFICHAGE ---
    for i in range(4):
        if stats["attaque"][i]["prises"] > 0:
            stats["attaque"][i]["marge_moyenne"] /= stats["attaque"][i]["prises"]
            stats["attaque"][i]["bouts_moyens"] /= stats["attaque"][i]["prises"]
        if stats["defense"][i]["parties"] > 0:
            stats["defense"][i]["marge_moyenne_subie"] /= stats["defense"][i]["parties"]

    print("\n" + "📊 "*8 + " PROFILAGE DU TOURNOI " + "📊 "*8)
    print(f"Donnes jouées   : {stats['parties_jouees']} / {nb_parties} ({stats['parties_annulees']} annulées)")
    print(f"📁 Un fichier 'pires_parties_mcts.txt' a été généré avec les logs des pires chutes.")

    print("\n🏆 CLASSEMENT DÉTAILLÉ (Score Global)")
    classement = sorted(stats["score_tournoi"].items(), key=lambda item: item[1], reverse=True)

    for rang, (id_joueur, score) in enumerate(classement):
        nom_modele = matchup[id_joueur]
        att = stats["attaque"][id_joueur]
        prcnt_victoire = (att['gagnees'] / att['prises'] * 100) if att['prises'] > 0 else 0
        
        print(f"\n{rang+1}er | J{id_joueur} [{nom_modele}] : {score:+.1f} points")
        print(f"  ⚔️  ATTAQUE ({att['prises']} contrats) : {prcnt_victoire:.1f}% de réussite")
        print(f"      -> Victoires: {att['gagnees']} | Chutes: {att['chutes']} (dont {att['chutes_graves']} graves)")
        print(f"      -> Marge Moy. : {att['marge_moyenne']:+.1f} pts | Bouts sauvés/capturés : {att['bouts_moyens']:.1f} / 3")
        print(f"  🛡️  DÉFENSE ({stats['defense'][id_joueur]['parties']} parties jouées)")
        print(f"      -> Résistance : L'attaquant adverse fait en moyenne {stats['defense'][id_joueur]['marge_moyenne_subie']:+.1f} pts contre lui")

    print("="*60 + "\n")

def obtenir_score_j0(partie, resultat):
    """ Extrait le score officiel du joueur 0 (qu'il soit attaquant ou défenseur) """
    if not resultat or len(resultat) != 3: return 0.0
    marge, annulee, preneur_id = resultat
    if annulee: return 0.0

    score_preneur, score_defenseur = partie.score_manche(marge)
    if preneur_id == 0:
        return score_preneur
    else:
        return score_defenseur

def evaluer_duplicata(nb_parties=50):
    import sys
    import os
    import random
    import io

    print("\n" + "="*60)
    print(f"🚀 TOURNOI DUPLICATA (GOMMAGE DE LA CHANCE) : {nb_parties} donnes.")
    print("Univers A : MCTS (J0) vs IA_2 | Univers B : IA_2 (J0) vs IA_2")
    print("Calcul en cours (les chutes du MCTS seront logguées dans 'pires_parties_mcts.txt')...")
    print("="*60)

    score_total_mcts = 0.0
    score_total_ia2 = 0.0
    victoires_mcts = 0
    victoires_ia2 = 0
    egalites = 0

    original_stdout = sys.stdout

    # On réinitialise le fichier d'autopsie au début du tournoi
    with open("pires_parties_mcts.txt", "w", encoding="utf-8") as f:
        f.write("=== ARCHIVE DES PIRES PARTIES DU MCTS (MODE DUPLICATA) ===\n")
        f.write("Seules les parties où le MCTS a pris un contrat et a chuté sont enregistrées ici.\n\n")

    try:
        for i in range(nb_parties):
            # On fige une graine aléatoire pour cette donne
            seed = random.randint(0, 1000000)

            # --- UNIVERS A : Le MCTS affronte la donne ---
            random.seed(seed)
            partie_A = Partie()
            
            # MAGNÉTOPHONE : On capture la console de l'Univers A
            capture_A = io.StringIO()
            sys.stdout = capture_A
            
            res_A = partie_A.partie(nb_tour=18, dif=["MCTS", 2, 2, 2], nb_donne=i+1, donneur=i%4)
            score_A = obtenir_score_j0(partie_A, res_A)

            # Si le MCTS était preneur et qu'il a une marge négative (chute), on sauvegarde l'enregistrement !
            if res_A and not res_A[1]: # Si la partie n'est pas annulée
                marge_A, _, preneur_A = res_A
                if preneur_A == 0 and marge_A < 0:
                    with open("pires_parties_mcts.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n{'='*20} DONNE DUPLICATA n°{i+1} : CHUTE (Marge: {marge_A}) {'='*20}\n")
                        f.write(capture_A.getvalue())

            # --- UNIVERS B : L'IA_2 affronte la MÊME donne ---
            random.seed(seed)
            partie_B = Partie()
            
            # TROU NOIR : On ne veut pas sauvegarder les logs de l'IA_2
            sys.stdout = open(os.devnull, 'w', encoding='utf-8')
            
            res_B = partie_B.partie(nb_tour=18, dif=[2, 2, 2, 2], nb_donne=i+1, donneur=i%4)
            score_B = obtenir_score_j0(partie_B, res_B)

            # --- COMPARAISON DE COMPÉTENCE PURE ---
            score_total_mcts += score_A
            score_total_ia2 += score_B

            if score_A > score_B:
                victoires_mcts += 1
            elif score_B > score_A:
                victoires_ia2 += 1
            else:
                egalites += 1

    finally:
        sys.stdout = original_stdout
        random.seed() # On libère l'aléatoire pour la suite

    print("\n" + "📊 "*8 + " RÉSULTATS DUPLICATA " + "📊 "*8)
    print(f"Donnes clonées jouées : {nb_parties}")
    print(f"Score Total MCTS (J0) : {score_total_mcts:+.1f} pts")
    print(f"Score Total IA_2 (J0) : {score_total_ia2:+.1f} pts")
    print("-" * 50)
    
    delta = score_total_mcts - score_total_ia2
    if delta > 0:
        print(f"✅ Le MCTS est NETTEMENT SUPÉRIEUR (+{delta:+.1f} pts de compétence pure)")
    else:
        print(f"❌ Le MCTS est ENCORE INFÉRIEUR ({delta:+.1f} pts de compétence pure)")
        
    print("-" * 50)
    print(f"Duels gagnés par le MCTS : {victoires_mcts}")
    print(f"Duels gagnés par l'IA_2  : {victoires_ia2}")
    print(f"Égalités (Même score)    : {egalites}")
    print("="*60 + "\n")

# Lancement de l'évaluation
if __name__ == "__main__":
    #conda activate tarot_ia
    OPTION_1 = False  # Mettre à True pour lancer l'évaluation automatique
    #OPTION_1 = True  # Mettre à True pour lancer l'évaluation automatique

    # ---------------------------------------------------------
    # OPTION 1 : Lancer le script d'évaluation (statistiques)
    # ---------------------------------------------------------
    if OPTION_1:
        evaluer_duplicata(nb_parties=100)
        #evaluer_modeles(nb_parties=50, matchup=["MCTS", 2, 2, 2])

    # ---------------------------------------------------------
    # OPTION 2 : Lancer UNE SEULE partie détaillée avec les logs
    # ---------------------------------------------------------
    else:
        print("Démarrage d'une partie de test...")
        une_partie = Partie()
        #On met l'IA MCTS (le cerveau) en Joueur 0, et des IA_2 basiques en face
        une_partie.partie(nb_tour=18, dif=["MCTS", 2, 2, 2], nb_donne=1)