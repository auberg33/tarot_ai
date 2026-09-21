from engine.jeu import ET_logique,OU_logique,COULEURS,ANNONCES,Historique,Jeu,factorielle,transpose,SOMME,MULT
import random

class JOUEUR:
    def __init__(self, jeu, id):
        self.jeu=Jeu(jeu) # jeu du joueur
        self.identifiant=id # identifiant du joueur pour la partie
        self.preneur=None # identifiant joueur qui prend
        self.poignee=0 # potentielle poignee d'atouts du joueur 

    def info_preneur(self,id:int): # permet de donner l'id du preneur au joueur
        self.preneur=id
        return

    def memoriser_chien(self, chien_cartes):
      """Mémorise les cartes du Chien révélé lors d'une Prise ou d'une Garde"""
      self.chien_revele = [(c.valeur, c.couleur) for c in chien_cartes]

    def carte_jouable(self,cartes_jouees:list): # prend la liste des cartes jouées lors du début du tour et renvoi la liste des cartes que je joueur peut jouer
        if len(cartes_jouees)==0: # premier joueur
            return self.jeu.cartes
        elif cartes_jouees[0].valeur==0 and cartes_jouees[0].couleur=='atout': # si la première carte est l'excuse
            if len(cartes_jouees)==1: # deuxième joueur
                return self.jeu.cartes
            else:
                carte_maitre=cartes_jouees[1]
        else:
            carte_maitre=cartes_jouees[0]

        # regarde quelle carte il peut jouer
        if carte_maitre.couleur in COULEURS: # pas d'atout
            possibilitees=[carte for carte in self.jeu.cartes if (carte.couleur==carte_maitre.couleur) or (carte.couleur=='atout' and carte.valeur==0)]
            if len(possibilitees)==0:
                possibilitees=[carte for carte in self.jeu.cartes if carte.couleur=="atout"]
                if len(possibilitees)==0:
                    possibilitees=self.jeu.cartes
        else: # la première carte est un atout
            possibilitees=[carte for carte in self.jeu.cartes if ET_logique([carte.couleur=='atout' and ((carte.valeur>c0.valeur and c0.couleur=='atout') or c0.couleur!='atout') for c0 in cartes_jouees])] # atouts entre celui joué et 21
            if len(possibilitees)==0:
                possibilitees=[carte for carte in self.jeu.cartes if carte.couleur=='atout' and carte.valeur!=0] # enlève l'excuse # atouts entre 1 et celui joué
            if len(possibilitees)==0:
                possibilitees=self.jeu.cartes
        return possibilitees

    def encheres(self,annonce): # liste des annonces des premiers joueurs -> son annonce
        
        mon_annonce=self.evaluation_jeu()
        
        # regarde si je peux annoncer ou si qqu a déjà mieux
        if mon_annonce==ANNONCES[-1] or len(annonce)==0: # cas ou je passe ou que je suis premier à annoncer
            return mon_annonce
        
        h=[ANNONCES.index(a)>ANNONCES.index(mon_annonce) for a in annonce]
        r=True
        for h0 in h:
            r*=h0
        if r:
            return mon_annonce # je peux annoncer psk c'est mieux
        else:
            return ANNONCES[-1] # je passe

    def poignees(self): # éventuelle poignée du joueur
        if len(self.jeu.chercher_cartes(couleur="atout"))>=15:
            self.poignee=3 # triple poignée
        elif len(self.jeu.chercher_cartes(couleur="atout"))>=13:
            self.poignee=2 # double poignée
        elif len(self.jeu.chercher_cartes(couleur="atout"))>=10:
            self.poignee=1 # simple poignée
        return self.poignee

class IA_2(JOUEUR):
    def __init__(self, jeu, id):
        JOUEUR.__init__(self, jeu, id)

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
    
    def joueur_coupe(self,historique:Historique,id_joueur:int,couleur=[]): # détermine si un joueur coupe dans une couleur
        # cas ou on le fait sur nous
        coupe=[False for i in COULEURS] # liste de booléens pour chaque couleur
        if id_joueur==self.identifiant:
            if OU_logique([carte.couleur=="atout" for carte in self.jeu.cartes]):
                for carte in self.jeu.cartes:
                    if carte.couleur!="atout":
                        coupe[COULEURS.index(carte.couleur)]=True


        else:
            # cas sur les autres joueurs
            coupe=[False for i in COULEURS] # liste de booléens pour chaque couleur
            for i,pli in enumerate(historique.storage_plis):
                premiere_carte=historique.pli_joue(i)[0]
                carte_joueur=historique.pli_trier(i)[id_joueur]
                
                # n'a pas d'atouts et se défausse
                if carte_joueur.couleur not in ["atout",premiere_carte.couleur]:
                    coupe=[False for i in COULEURS]
                    if couleur==[]:
                        return coupe # liste de booléens correpondant à chaque couleur
                    else:
                        return coupe[COULEURS.index(couleur)]
                
                # peut possèder des atouts mais on sait qu'il coupe
                if premiere_carte.couleur in COULEURS and carte_joueur.couleur=="atout":
                    coupe[COULEURS.index(premiere_carte.couleur)]=True
                elif premiere_carte.couleur in COULEURS and premiere_carte.couleur==carte_joueur.couleur:
                    coupe[COULEURS.index(premiere_carte.couleur)]=False

            # si toutes les cartes ont été jouées ou sont dans mon jeu
            compte=[0 for i in COULEURS]
            for pli in historique.storage_plis:
                for carte in pli:
                    if carte.couleur!="atout":
                        compte[COULEURS.index(carte.couleur)]+=1
            for carte in self.jeu.cartes:
                if carte.couleur!="atout":
                    compte[COULEURS.index(carte.couleur)]+=1
            
            l=[]
            for i in range(len(compte)):
                if compte[i]==14:
                    coupe[i]=True
                else:
                    coupe[i]==False
                        
        if couleur==[]:
            return coupe # liste de booléens correpondant à chaque couleur
        else:
            return coupe[COULEURS.index(couleur)]

    def maitre_couleur(self,historique:Historique,couleur,id_joueur=None): # détermine si l'équipe d'un joueur est maître dans une couleur (sans prendre en compte les coupes)
        if id_joueur==None:
            id_joueur=self.identifiant
        
        # obtention des adversaires
        if id_joueur!=self.preneur:
            adversaires=[self.preneur]
            equipe=[i for i in range (4) if i!=self.preneur]
        else:
            adversaires=[i for i in range (4) if i!=self.preneur]
            equipe=[self.preneur]

        # étude du pli en cours
        pli_en_cours=historique.storage_pli_en_cours
        id_commence=historique.storage_premier_joueur[-1] # celui qui a commencé

        # identifiants joueurs ayant participé au pli en cours
        joueurs=[(id_commence+k)%4 for k in range(len(pli_en_cours))]
        cartes_adversaires=[pli_en_cours[i] for i in joueurs if joueurs in adversaires]
        cartes_equipe=[pli_en_cours[i] for i in joueurs if joueurs in equipe]

        # savoir si les adversaires ont déjà joué
        preneur_deja_joue=(id_joueur==self.preneur)*(len(pli_en_cours)==3)
        defenseur_deja_joue=(id_joueur==self.preneur)*(self.preneur in [(id_commence+i)%4 for i in range(len(pli_en_cours))])
        adversaires_deja_joue=OU_logique([preneur_deja_joue,defenseur_deja_joue])

        lcarte=[] # cartes déjà jouées dans la couleur
        for pli in historique.storage_plis:
            for carte in pli:
                if carte.couleur==couleur:
                    lcarte.append(carte)

        # meilleures cartes dans la couleur demandée
        notre_carte_maitre=self.jeu.carte_max(couleur) # carte maître du joueur dans la couleur
        carte_maitre_couleur=Jeu(lcarte).complementaire().carte_max(couleur) # carte maître du jeu dans la couleur
        equipe_carte_maitre=Jeu(cartes_adversaires).carte_max(couleur) # carte maître de l'équipe dans la couleur
        adversaires_carte_maitre=Jeu(cartes_adversaires).carte_max(couleur) # carte maître des adversaires dans la couleur

        # les adversaires ont la meilleure carte possible
        if adversaires_carte_maitre==carte_maitre_couleur:
            return False # certitude

        if adversaires_deja_joue: # tous nos adversaires ont déjà posé une carte durant le tour
             # notre équipe ou nous avons une meilleure carte que la meilleure carte des adversaires
            if len(cartes_adversaires)>0 and Jeu(cartes_adversaires+[notre_carte_maitre]+cartes_equipe).maitre()>Jeu(cartes_adversaires).maitre():
                return True # certitude
            # tous les adversaires ont joué et sont pour l'instant maîtres, dans le doute on n'est pas maître
            else:
                return False # à améliorer dans l'IA évoluée
        
        else: # tous les adversaires n'ont pas encore joué et ils n'ont pas posé la meilleure carte possible
            if notre_carte_maitre==carte_maitre_couleur: # on a la meilleure carte possible
                return True # certitude
            if equipe_carte_maitre==carte_maitre_couleur: # notre équipe a joué la meilleure carte
                return True # certitude
            else: # notre équipe est pour l'instant maître, dans le doute on est maître
                return self.maitre_couleur_proba(historique,couleur,id_joueur)
                # if len(cartes_adversaires)>0 and Jeu(cartes_adversaires+[notre_carte_maitre]+cartes_equipe).maitre()>Jeu(cartes_adversaires).maitre():
                #     return True # probabilité
                # else:
                #     return False # probabilité

    def maitre_couleur_proba(self,historique:Historique,couleur,id): # maitre couleur probabiliste
        valeur=self.jeu.maitre()
        
        # détermine les cartes que peuvent possèder mes adversaires

        def cartes_possibles(couleur_absentes): # renvoie les cartes qui n'ont pas été jouées qui ne sont pas des couleurs_absentes
            cartes_en_jeu=Jeu() # crée un jeu vide
            cartes_en_jeu.initialiser()
            cartes_en_jeu=cartes_en_jeu.cartes
            cartes_deja_jouees=[]
            for pli in historique.storage_plis: # récupère les cartes déjà jouées
                for carte in pli:
                    cartes_deja_jouees.append(carte)
            for carte in historique.storage_pli_en_cours: # récupère les cartes qui viennent d'être jouées
                cartes_deja_jouees.append(carte)
            for carte in self.jeu.cartes: # récupère mes cartes
                cartes_deja_jouees.append(carte)

            new_cartes_en_jeu=cartes_en_jeu[:]
            for carte in cartes_en_jeu: # conserve uniquement les cartes pas encore jouées et qui sont d'une couleur présente
                for carte2 in cartes_deja_jouees:
                    if ((carte.valeur==carte2.valeur and carte.couleur==carte2.couleur) or (carte.couleur in couleur_absentes)) and carte in new_cartes_en_jeu:
                        new_cartes_en_jeu.remove(carte)
            return new_cartes_en_jeu
    
        def cartes_restantes_couleur(couleur): # renvoie les cartes de la couleur qui n'ont pas encore été jouées
            couleur_absentes=[c for c in COULEURS+["atout"] if c!=couleur]
            return cartes_possibles(couleur_absentes)

        def info_coupe(id): # renvoie dans quelle couleur le joueur id a déjà coupé et s'il a déjà défaussé (=plus d'atouts)
            coupe=[False for i in COULEURS] # liste de booléens pour chaque couleur / est ce qu'il a deja coupé dans cette couleur
            at=True # liste de booléens pour chaque couleur / est ce qu'il lui reste potentiellement de atouts
            for i,pli in enumerate(historique.storage_plis):
                premiere_carte=historique.pli_joue(i)[0]
                carte_joueur=historique.pli_trier(i)[id]
                
                # n'a pas d'atouts et se défausse
                if carte_joueur.couleur not in ["atout",premiere_carte.couleur]:
                    at=False
                
                # peut possèder des atouts mais on sait qu'il coupe
                if premiere_carte.couleur in COULEURS and carte_joueur.couleur=="atout":
                    coupe[COULEURS.index(premiere_carte.couleur)]=True
                elif premiere_carte.couleur in COULEURS and premiere_carte.couleur==carte_joueur.couleur:
                    coupe[COULEURS.index(premiere_carte.couleur)]=False
            return coupe,at
        
        # liste des joueurs adverses qui jouent après moi
        N=18-len(historique.storage_plis) #nb de tour restant
        if self.identifiant==self.preneur:
            liste_joueur_adversaire_restant=[(self.identifiant+k)%4 for k in range (1,4-len(historique.storage_pli_en_cours))]
        else:
            if self.preneur in [(self.identifiant+k)%4 for k in range (1,4-len(historique.storage_pli_en_cours))]:
                liste_joueur_adversaire_restant=[self.preneur]
            else:
                liste_joueur_adversaire_restant=[] # pk on se pose la question ?

        # cartes de la couleur, restantes
        cartes_reste=cartes_restantes_couleur(couleur)
        tableau_proba=[]
        if len(liste_joueur_adversaire_restant)==0:
            vmax=max([carte.valeur for carte in historique.storage_pli_en_cours])
            return vmax<valeur

        for joueur in liste_joueur_adversaire_restant:
            ligne_proba=[]
            coupe,at=info_coupe(joueur)
            if not at: # il n'a pas d'atout(s)
                if coupe[COULEURS.index(couleur)]: # si le joueur a déjà coupé dans cette couleur
                    for cette_carte in cartes_reste:
                        ligne_proba.append(0)
                else:
                    couleur_absentes=[c for i,c in enumerate(COULEURS) if coupe[i]]+["atout"] # couleurs que le joueur n'a pas
                    cartes_possible=cartes_possibles(couleur_absentes)
                    L=len(cartes_possible) # nombre de cartes possibles
                    
                    # estime la probabilité que "joueur" ai "cette_carte"
                    for cette_carte in cartes_reste:
                        p=N/L
                        ligne_proba.append(p)
            else:
                couleur_absentes=[c for i,c in enumerate(COULEURS) if coupe[i]] # couleurs que le joueur n'a pas
                cartes_possible=cartes_possibles(couleur_absentes)
                L=len(cartes_possible) # nombre de cartes possibles

                # proba qu'il lui reste des cartes de la couleur
                nc=cartes_possibles([c for c in COULEURS+["atout"] if c!=couleur]) # carte de la couleur
                nc=len(nc)

                # proba qu'il coupe
                A0=cartes_possibles(COULEURS) # nombre d'atout restant hors excuse
                A=len(cartes_possibles(COULEURS))-len(Jeu(A0).chercher_cartes(0,"atout"))
                if L-A<N: # on est sur qu'il ai un atout psk il reste pas assez de cartes opour faire autrement
                    p_coupe=1
                elif L-nc<N: # on est sur qu'il ai de la couleur psk il reste pas assez de cartes opour faire autrement
                    p_coupe=0
                else:
                    p_coupe=(1-factorielle(L-A,N)/factorielle(L,N))*factorielle(L-nc,N)/factorielle(L,N)

                # estime la probabilité que "joueur" ai "cette_carte" et ne coupe pas
                for cette_carte in cartes_reste:
                    p=N/L
                    ligne_proba.append(p*(1-p_coupe)+p_coupe)
            tableau_proba.append(ligne_proba)
        
        # tirage
        tableau_proba=transpose(tableau_proba)
        Synthese_proba=[1-MULT([1-p for p in m]) for m in tableau_proba] # vecteur des probas que aucun des prochains joueurs ai la carte

        P=SOMME([Synthese_proba[i] for i,u in enumerate(cartes_reste) if u.valeur>valeur]) # proba que l'un des prochains joueur ai une meilleur carte
        n=0.1 # indice de risque

        return (random.random()>P**n)
    
    def choix_chien_ff(self,chien:Jeu): # le joueur fait son chien
        jeu=Jeu(self.jeu.cartes+chien.cartes)
        nv_chien=[]

        compte_couleur=[len(jeu.chercher_cartes(couleur=i)) for i in COULEURS]
        compte_roi=[len(jeu.chercher_cartes(valeur=14,couleur=i)) for i in COULEURS]

        # Partie 1 : met au chien le max des couleurs min sans roi
        for k in range (len(COULEURS)): # analyse toutes les couleurs
            for j in range (len(COULEURS)): # compare toutes les couleurs
                if compte_couleur[j]==min(compte_couleur) and compte_roi[j]==0:
                    i=13
                    while len(nv_chien)<6 and i>0:
                        l=jeu.chercher_cartes(valeur=i,couleur=COULEURS[j])
                        if len(l)==1:
                            nv_chien.append(l[0])
                        i-=1
                    compte_couleur[j]=100
        
        # Partie 2 : si on a les 4 rois, met au chien le max des couleurs min sans roi
        for k in range (len(COULEURS)): # analyse toutes les couleurs
            for j in range (len(COULEURS)): # compare toutes les couleurs
                if compte_couleur[j]==min(compte_couleur):
                    i=13
                    while len(nv_chien)<6 and i>0:
                        l=jeu.chercher_cartes(valeur=i,couleur=COULEURS[j])
                        if len(l)==1:
                            nv_chien.append(l[0])
                        i-=1
                    compte_couleur[j]=100
        
        # Partie 3 : si on a 4 rois et pas assez de carte hors atouts
        i=2
        while len(nv_chien)<6:
            l=jeu.chercher_cartes(valeur=i,couleur="atout")
            if len(l)==1:
                nv_chien.append(l[0])
            i+=1
        
        # met les autres cartes dans le jeu du joueur
        l=[]
        self.jeu.cartes=[]

        for carte in jeu.cartes:
            if (carte.valeur,carte.couleur) not in [(c.valeur,c.couleur) for c in nv_chien]:
                self.jeu.cartes.append(carte)

        return Jeu(nv_chien)

    def choix_carte(self,cartes_jouees:list,historique:Historique): # décide quelle carte il va jouer à ce tour
        possibilitees=self.carte_jouable(cartes_jouees)

        if len(cartes_jouees)+1 in [1]: # premier joueur
            if self.identifiant==self.preneur: # cas du preneur
                cartes_couleur=[Jeu(possibilitees).chercher_cartes(couleur=c) for c in COULEURS]
                if SOMME([len(i) for i in cartes_couleur])!=0:
                    index_longue=[len(i) for i in cartes_couleur].index(max([len(i) for i in cartes_couleur]))
                    jeu_longue=Jeu(cartes_couleur[index_longue]) # récupère la longue
                    couleur_longue=jeu_longue.cartes[0].couleur
                    if OU_logique([self.joueur_coupe(historique,id,couleur=couleur_longue) for id in range (4) if id!=self.identifiant]): # vrai si un des défenseurs coupe
                        return self.joue(jeu_longue.carte_min(couleur=couleur_longue))
                    else:
                        if self.maitre_couleur(historique,couleur_longue,self.identifiant): # aucun défenseur ne coupe et le preneur a la meilleur carte
                            return self.joue(jeu_longue.carte_max(couleur=couleur_longue))
                        else:
                            return self.joue(jeu_longue.carte_min(couleur=couleur_longue))
                else:
                    if len([carte for carte in possibilitees if carte.couleur not in COULEURS if carte.valeur!=1])!=0: # il lui reste un autre atout que le 1 
                        return self.joue(Jeu([carte for carte in possibilitees if carte.valeur!=1]).carte_min("atout"))
                    else:
                        return self.joue(Jeu(possibilitees).carte_min("atout")) # jete le 1
            else: # défenseurs
                coupe_preneur=self.joueur_coupe(historique,self.preneur)
                cartes_couleur=[Jeu(possibilitees).chercher_cartes(couleur=c) for c in COULEURS]
                cartes_couleur_non_habillees=[Jeu(possibilitees).chercher_cartes(couleur=c, valeur=[i+1 for i in range (10)]) for c in COULEURS]
                roi=[Jeu(possibilitees).chercher_cartes(couleur=c, valeur=14) for c in COULEURS]
                nous_maitre=[self.maitre_couleur(historique,c,self.identifiant) for c in COULEURS]
                atouts=Jeu(possibilitees).chercher_cartes(couleur="atout")
                petit=Jeu(possibilitees).chercher_cartes(couleur="atout",valeur="1")

                condition_1=[coupe_preneur[i]*(len(cartes_couleur_non_habillees[i])!=0) for i in range(len(COULEURS))] # vrai si le preneur coupe et que j'ai des cartes non habillées de cette couleur
                condition_2=[(len(cartes_couleur_non_habillees[i])!=0)*(1-(len(roi[i])!=0)) for i in range(len(COULEURS))] # vrai si le défenseur a des petites cartes dans une couleur ou il n'a pas le roi
                condition_3=[(len(cartes_couleur[i])!=0)*nous_maitre[i]*(1-coupe_preneur[i]) for i in range(len(COULEURS))] # vrai si le preneur ne coupe pas et qu'on est maitre
                
                if OU_logique(condition_1):
                    id_couleur=condition_1.index(max(condition_1))
                    return self.joue(Jeu(cartes_couleur_non_habillees[id_couleur]).carte_min())
                elif OU_logique(condition_2):
                    id_couleur=condition_2.index(max(condition_2))
                    return self.joue(Jeu(cartes_couleur[id_couleur]).carte_min())
                elif OU_logique(condition_3):
                    id_couleur=condition_3.index(max(condition_3))
                    return self.joue(Jeu(cartes_couleur[id_couleur]).carte_max())
                elif len(atouts)-len(petit)!=0: # au moins un atout autre que le petit
                    return self.joue(Jeu(atouts).carte_min())
                elif SOMME([len(i) for i in cartes_couleur])>0:
                    return self.joue(Jeu(possibilitees).carte_min())
                else:
                    return self.joue(petit)
                      
        elif len(cartes_jouees)+1 in [2,3]: # deuxième ou troisième joueur
            #  prendre en compte le fait qu'on peut deja savoir si on va gagner le pli et mettre la carte avec la plus grande valeur

            if cartes_jouees[0].couleur in COULEURS and len([carte for carte in possibilitees if carte.couleur==cartes_jouees[0].couleur])!=0: # une couleur est demandée et on a la couleur
                if self.maitre_couleur(historique,cartes_jouees[0].couleur,self.identifiant)==True: # on est maitre à la couleur demandée
                    return self.joue(Jeu(possibilitees).carte_max(cartes_jouees[0].couleur))
                else:
                    return self.joue(Jeu(possibilitees).carte_min(cartes_jouees[0].couleur))
            
            if len([carte for carte in possibilitees if carte.couleur not in COULEURS])!=0: # on a des atouts               
                val_min=Jeu(cartes_jouees).carte_max("atout")
                if val_min==None:
                    val_min=-1
                else:
                    val_min=val_min.valeur
                atouts_sup=[carte for carte in possibilitees if carte.valeur>val_min and carte.couleur not in COULEURS]

                if len(atouts_sup)>0:
                    return self.joue(Jeu(atouts_sup).carte_min("atout"))
                else:
                    if len([carte for carte in possibilitees if carte.couleur not in COULEURS if carte.valeur!=1])!=0: # il lui reste un autre atout que le 1 
                        return self.joue(Jeu([carte for carte in possibilitees if carte.valeur!=1]).carte_min("atout"))
                    else:
                        return self.joue(Jeu(possibilitees).carte_min("atout")) # jete le 1 
            else:
                carte_p=[[carte for carte in possibilitees if carte.couleur==c if carte.valeur<=10] for c in COULEURS] # trie les petites cartes par couleur

                if OU_logique([len(carte_p)!=0]): # on a une couleur avec des petites cartes
                    # cherche l'indice des couleurs sans habillés
                    couleur_possibles=[i for i in range (len(COULEURS)) if len(carte_p[i])!=0]
                else: # il ne nous reste que des habillés
                    couleur_possibles=[]
                    p=11
                    while len(couleur_possibles)==0 and p<15:
                        couleur_habilles=[[carte for carte in possibilitees if carte.couleur==c if carte.valeur==p] for c in COULEURS] # trie les habillés par couleur
                        p+=1
                        couleur_possibles=[i for i in range (len(COULEURS)) if len(couleur_habilles[i])!=0]
                
                # liste des adversaires
                if self.preneur==self.identifiant:
                    adversaires=[i for i in range (4) if i!=self.identifiant]
                else:
                    adversaires=[self.preneur]
                
                # cherche dans quelle couleur le maximum d'adversaire coupe
                nb_coupe_adv=[SOMME([self.joueur_coupe(historique,i)[j] for i in adversaires]) for j in couleur_possibles]
                if OU_logique([nb_coupe_adv]): #qqu coupe
                    couleur_jouee=COULEURS[couleur_possibles[nb_coupe_adv.index(max(nb_coupe_adv))]]
                    return self.joue(Jeu(possibilitees).carte_min(couleur_jouee))
                else: #personne coupe
                    return self.joue(Jeu(possibilitees).carte_min())

        elif len(cartes_jouees)+1 in [4]: # dernier joueur
            atout_jouees = len([carte for carte in cartes_jouees if carte.couleur == 'atout'])  # Regarde si il y a un atout dans les cartes jouées        
            # Le joueur est preneur
            if self.identifiant==self.preneur or (Jeu(cartes_jouees).maitre()==self.preneur)*(self.identifiant!=self.preneur): # preneur
                if cartes_jouees[0].couleur in COULEURS and len([carte for carte in possibilitees if carte.couleur==cartes_jouees[0].couleur])!=0: # une couleur est demandée et on a la couleur
                        if self.maitre_couleur(historique,cartes_jouees[0].couleur,self.identifiant)==True: # on est maitre à la couleur demandée
                            return self.joue(Jeu(possibilitees).carte_max(cartes_jouees[0].couleur))
                        else:
                            return self.joue(Jeu(possibilitees).carte_min(cartes_jouees[0].couleur))
                
                # Si le joueur coupe et une couleur est demandée
                elif len([carte for carte in possibilitees if carte.couleur not in COULEURS])!=0: # on a des atouts
                    val_min=Jeu(cartes_jouees).carte_max("atout")
                    if val_min==None:
                        val_min=-1
                    else:
                        val_min=val_min.valeur
                    atouts_sup=[carte for carte in possibilitees if carte.valeur>val_min and carte.couleur not in COULEURS]

                    if len(atouts_sup)>0:
                        return self.joue(Jeu(atouts_sup).carte_min("atout"))
                    else:
                        if len([carte for carte in possibilitees if carte.couleur not in COULEURS if carte.valeur!=1])!=0: # il lui reste un autre atout que le 1 
                            return self.joue(Jeu([carte for carte in possibilitees if carte.valeur!=1]).carte_min("atout"))
                        else:
                            return self.joue(Jeu(possibilitees).carte_min("atout")) # jete le 1                            

                # on défausse (une petite carte)
                else:
                    return self.joue(Jeu(possibilitees).carte_min())
                  
            
            else: # le joueur est défenseur et ils gagnent (on veut maximiser les points)
                if cartes_jouees[0].couleur in COULEURS and len([carte for carte in possibilitees if carte.couleur==cartes_jouees[0].couleur])!=0: # une couleur est demandée et on a la couleur
                    return self.joue(Jeu(possibilitees).carte_max(cartes_jouees[0].couleur))
                
                # Si le joueur coupe et une couleur est demandée
                elif len([carte for carte in possibilitees if carte.couleur not in COULEURS])!=0: # on a des atouts
                    val_min=Jeu(cartes_jouees).carte_max("atout")
                    if val_min==None:
                        val_min=-1
                    else:
                        val_min=val_min.valeur
                    atouts_sup=[carte for carte in possibilitees if carte.valeur>val_min and carte.couleur not in COULEURS]

                    if len(atouts_sup)>0:
                        return self.joue(Jeu(atouts_sup).carte_min("atout"))
                    else:
                        return self.joue(Jeu(possibilitees).carte_min("atout"))
                    
                # on défausse (une grosse carte)
                else:
                    return self.joue(Jeu(possibilitees).carte_max())
                            
        # if False: # dernier joueur
        #     # liste des adversaires
        #     if self.preneur==self.identifiant:
        #         adversaires=[i for i in range (4) if i!=self.identifiant]
        #     else:
        #         adversaires=[self.preneur]
            
        #     # si on est en train de gagner
        #     if (Jeu(cartes_jouees).maitre()+historique.dernier_gagnant())%4 not in adversaires:
        #         # suite a revoir j'ai pas compris le graphe
        #         pass
        #     return                
    
    def choix_chien(self,chien:Jeu): # le joueur fait son chien
        jeu=Jeu(self.jeu.cartes+chien.cartes)
        nv_chien=[]

        compte_couleur=[len(jeu.chercher_cartes(couleur=i)) for i in COULEURS]
        compte_roi=[len(jeu.chercher_cartes(valeur=14,couleur=i)) for i in COULEURS]

        # Partie 1 : met au chien le max des couleurs min sans roi
        for k in range (len(COULEURS)): # analyse toutes les couleurs
            for j in range (len(COULEURS)): # compare toutes les couleurs
                if compte_couleur[j]==min(compte_couleur) and compte_roi[j]==0:
                    i=13
                    while len(nv_chien)<6 and i>0:
                        l=jeu.chercher_cartes(valeur=i,couleur=COULEURS[j])
                        if len(l)==1:
                            nv_chien.append(l[0])
                        i-=1
                    compte_couleur[j]=100
        
        # Partie 2 : si on a les 4 rois, met au chien le max des couleurs min sans roi
        for k in range (len(COULEURS)): # analyse toutes les couleurs
            for j in range (len(COULEURS)): # compare toutes les couleurs
                if compte_couleur[j]==min(compte_couleur):
                    i=13
                    while len(nv_chien)<6 and i>0:
                        l=jeu.chercher_cartes(valeur=i,couleur=COULEURS[j])
                        if len(l)==1:
                            nv_chien.append(l[0])
                        i-=1
                    compte_couleur[j]=100
        
        # Partie 3 : si on a 4 rois et pas assez de carte hors atouts
        i=2
        while len(nv_chien)<6:
            l=jeu.chercher_cartes(valeur=i,couleur="atout")
            if len(l)==1:
                nv_chien.append(l[0])
            i+=1
        
        # met les autres cartes dans le jeu du joueur
        l=[]
        self.jeu.cartes=[]

        for carte in jeu.cartes:
            if (carte.valeur,carte.couleur) not in [(c.valeur,c.couleur) for c in nv_chien]:
                self.jeu.cartes.append(carte)

        return Jeu(nv_chien)

    def joue(self,carte_jouee): #simple fonction qui évite d'oubier de supprimer la carte du jeu quand on la joue
        carte_jouee=self.jeu.supprimer(carte_jouee)
        return carte_jouee

class IA_1(JOUEUR):
    def __init__(self, jeu, id):
        JOUEUR.__init__(self, jeu, id)
    
    def evaluation_jeu(self):
        evaluation=0

        # 1 point par atout
        evaluation+=len(self.jeu.chercher_cartes(couleur="atout"))

        # ajoute 2 points supplémentaire pour les bouts
        evaluation+=2*len(self.jeu.chercher_cartes(0,"atout")+self.jeu.chercher_cartes(1,"atout")+self.jeu.chercher_cartes(21,"atout"))

        # ajoute 1 point par roi et 1 point supplémentaire s'il y la dame de la même couleur
        for couleur in COULEURS:
            if len(self.jeu.chercher_cartes(14,couleur))==1:
                evaluation+=1
                if len(self.jeu.chercher_cartes(13,couleur))==1:
                    evaluation+=1

        # ajoute 1 pt pour les couleurs de plus de 5 cartes et 2 pts pour les couleurs de plus de 8 cartes
        compte_couleur=[len(self.jeu.chercher_cartes(couleur=i)) for i in COULEURS]
        for j in compte_couleur:
            if j>8:
                evaluation+=2
            elif j>5:
                evaluation+=1
        
        # choisi mon annonce en fonction
        evaluation_min=[0,12,15,18,22] # evaluation minimale pour prendre une ANNONCE (attention l'ordre est inversé)

        for i,e in enumerate(evaluation_min):
            if evaluation>=e:
                mon_annonce=ANNONCES[-i-1]

        return mon_annonce
    
    def joueur_coupe(self,historique:Historique,id_joueur:int,couleur=[]): # détermine si un joueur coupe dans une couleur
        # cas ou on le fait sur nous
        coupe=[False for i in COULEURS] # liste de booléens pour chaque couleur
        if id_joueur==self.identifiant:
            if OU_logique([carte.couleur=="atout" for carte in self.jeu.cartes]):
                for carte in self.jeu.cartes:
                    if carte.couleur!="atout":
                        coupe[COULEURS.index(carte.couleur)]=True


        else:
            # cas sur les autres joueurs
            coupe=[False for i in COULEURS] # liste de booléens pour chaque couleur
            for i,pli in enumerate(historique.storage_plis):
                premiere_carte=historique.pli_joue(i)[0]
                carte_joueur=historique.pli_trier(i)[id_joueur]
                
                # n'a pas d'atouts et se défausse
                if carte_joueur.couleur not in ["atout",premiere_carte.couleur]:
                    coupe=[False for i in COULEURS]
                    if couleur==[]:
                        return coupe # liste de booléens correpondant à chaque couleur
                    else:
                        return coupe[COULEURS.index(couleur)]
                
                # peut possèder des atouts mais on sait qu'il coupe
                if premiere_carte.couleur in COULEURS and carte_joueur.couleur=="atout":
                    coupe[COULEURS.index(premiere_carte.couleur)]=True
                elif premiere_carte.couleur in COULEURS and premiere_carte.couleur==carte_joueur.couleur:
                    coupe[COULEURS.index(premiere_carte.couleur)]=False

            # si toutes les cartes ont été jouées ou sont dans mon jeu
            compte=[0 for i in COULEURS]
            for pli in historique.storage_plis:
                for carte in pli:
                    if carte.couleur!="atout":
                        compte[COULEURS.index(carte.couleur)]+=1
            for carte in self.jeu.cartes:
                if carte.couleur!="atout":
                    compte[COULEURS.index(carte.couleur)]+=1
            
            l=[]
            for i in range(len(compte)):
                if compte[i]==14:
                    coupe[i]=True
                else:
                    coupe[i]==False
                        
        if couleur==[]:
            return coupe # liste de booléens correpondant à chaque couleur
        else:
            return coupe[COULEURS.index(couleur)]

    def maitre_couleur_v2(self,historique:Historique,couleur,id_joueur:int): # détermine si l'équipe du joueur est maître
        autres_joueurs=[i for i in range (4) if i!=id_joueur]
        lcarte=[] # cartes déjà jouées dans la couleur
        for pli in historique.storage_plis:
            for carte in pli:
                if carte.couleur==couleur:
                    lcarte.append(carte)
        carte_maitre=Jeu(lcarte).complementaire().carte_max(couleur) # carte maître du jeu dans la couleur
        notre_carte_maitre=self.jeu.carte_max(couleur) # meilleure carte du joueur dans la couleur
        autres_coupes=OU_logique([self.joueur_coupe(joueur) for joueur in autres_joueurs]) # au moins un joueur coupe
        if not autres_coupes: # les autres ne coupent pas
            if notre_carte_maitre==carte_maitre: # j'ai la meilleure carte et personne ne coupe
                return True
            if self.joueur_coupe(id_joueur): # je suis le seul à couper
                return True
            else: # je ne coupe pas et je n'ai pas la meilleure carte
                return False
        else: # les autres coupent
            if not self.joueur_coupe(id_joueur): # je ne coupe pas mais les autres coupent
                return False
            else:
                carte_maitre_atout=Jeu(lcarte).complementaire().carte_max("atout") # carte maître du jeu dans la couleur
                notre_carte_maitre_atout=self.jeu.carte_max("atout") # meilleure carte du joueur dans la couleur
                if notre_carte_maitre_atout==carte_maitre_atout: # on coupe et on a le meilleur atout
                    return True
        return True # cas indéfini à traiter pour l'IA évoluée
            
    def maitre_couleur_v1(self,historique:Historique,couleur,id_joueur:int): # détermine si un joueur est maitre dans une couleur
        if id_joueur==self.identifiant:
            # liste des cartes jouées dans cette couleur
            lcarte=[]
            for pli in historique.storage_plis:
                for carte in pli:
                    if carte.couleur==couleur:
                        lcarte.append(carte)
            # max
            carte_maitre=Jeu(lcarte).complementaire().carte_max(couleur)
            notre_carte_maitre=self.jeu.carte_max(couleur)
            if notre_carte_maitre==carte_maitre:
                return True # on est sûr d'avoir la carte maximale du jeu
            else:
                return False
        else: # on regarde si un autre joueur est maitre dans une couleur
            if self.maitre_couleur(historique,couleur,self.identifiant)==True:
                return False # on est maître, donc l'autre joueur n'est pas maître
            elif self.joueur_coupe(historique,id_joueur,couleur):
                return False # le joueur coupe
            else:
                # si 2 coupent & que je suis pas maitre
                autres_joueurs=[j for j in range (4) if (j!=self.identifiant and j!=id_joueur)]
                if ET_logique([self.joueur_coupe(historique,i,couleur) for i in autres_joueurs]):
                    return True
        return True #'undefined' : possibilité d'estimer ?

    def maitre_couleur(self,historique:Historique,couleur,id_joueur=None): # détermine si l'équipe d'un joueur est maître dans une couleur (sans prendre en compte les coupes)
        if id_joueur==None:
            id_joueur=self.identifiant
        
        # obtention des adversaires
        if id_joueur!=self.preneur:
            adversaires=[self.preneur]
            equipe=[i for i in range (4) if i!=self.preneur]
        else:
            adversaires=[i for i in range (4) if i!=self.preneur]
            equipe=[self.preneur]

        # étude du pli en cours
        pli_en_cours=historique.storage_pli_en_cours
        id_commence=historique.storage_premier_joueur[-1] # celui qui a commencé

        # identifiants joueurs ayant participé au pli en cours
        joueurs=[(id_commence+k)%4 for k in range(len(pli_en_cours))]
        cartes_adversaires=[pli_en_cours[i] for i in joueurs if joueurs in adversaires]
        cartes_equipe=[pli_en_cours[i] for i in joueurs if joueurs in equipe]

        # savoir si les adversaires ont déjà joué
        preneur_deja_joue=(id_joueur==self.preneur)*(len(pli_en_cours)==3)
        defenseur_deja_joue=(id_joueur==self.preneur)*(self.preneur in [(id_commence+i)%4 for i in range(len(pli_en_cours))])
        adversaires_deja_joue=OU_logique([preneur_deja_joue,defenseur_deja_joue])

        lcarte=[] # cartes déjà jouées dans la couleur
        for pli in historique.storage_plis:
            for carte in pli:
                if carte.couleur==couleur:
                    lcarte.append(carte)

        # meilleures cartes dans la couleur demandée
        notre_carte_maitre=self.jeu.carte_max(couleur) # carte maître du joueur dans la couleur
        carte_maitre_couleur=Jeu(lcarte).complementaire().carte_max(couleur) # carte maître du jeu dans la couleur
        equipe_carte_maitre=Jeu(cartes_adversaires).carte_max(couleur) # carte maître de l'équipe dans la couleur
        adversaires_carte_maitre=Jeu(cartes_adversaires).carte_max(couleur) # carte maître des adversaires dans la couleur

        # les adversaires ont la meilleure carte possible
        if adversaires_carte_maitre==carte_maitre_couleur:
            return False # certitude

        if adversaires_deja_joue: # tous nos adversaires ont déjà posé une carte durant le tour
             # notre équipe ou nous avons une meilleure carte que la meilleure carte des adversaires
            if len(cartes_adversaires)>0 and Jeu(cartes_adversaires+[notre_carte_maitre]+cartes_equipe).maitre()>Jeu(cartes_adversaires).maitre():
                return True # certitude
            # tous les adversaires ont joué et sont pour l'instant maîtres, dans le doute on n'est pas maître
            else:
                return False # à améliorer dans l'IA évoluée
        
        else: # tous les adversaires n'ont pas encore joué et ils n'ont pas posé la meilleure carte possible
            if notre_carte_maitre==carte_maitre_couleur: # on a la meilleure carte possible
                return True # certitude
            if equipe_carte_maitre==carte_maitre_couleur: # notre équipe a joué la meilleure carte
                return True # certitude
            else: # notre équipe est pour l'instant maître, dans le doute on est maître
                if len(cartes_adversaires)>0 and Jeu(cartes_adversaires+[notre_carte_maitre]+cartes_equipe).maitre()>Jeu(cartes_adversaires).maitre():
                    return True # probabilité
                else:
                    return False # probabilité

    def joue(self,carte_jouee): #simple fonction qui évite d'oubier de supprimer la carte du jeu quand on la joue
        carte_jouee=self.jeu.supprimer(carte_jouee)
        return carte_jouee

    def choix_carte(self,cartes_jouees:list,historique:Historique): # décide quelle carte il va jouer à ce tour
        possibilitees=self.carte_jouable(cartes_jouees)

        if len(cartes_jouees)+1 in [1]: # premier joueur
            if self.identifiant==self.preneur: # cas du preneur
                cartes_couleur=[Jeu(possibilitees).chercher_cartes(couleur=c) for c in COULEURS]
                if SOMME([len(i) for i in cartes_couleur])!=0:
                    index_longue=[len(i) for i in cartes_couleur].index(max([len(i) for i in cartes_couleur]))
                    jeu_longue=Jeu(cartes_couleur[index_longue]) # récupère la longue
                    couleur_longue=jeu_longue.cartes[0].couleur
                    if OU_logique([self.joueur_coupe(historique,id,couleur=couleur_longue) for id in range (4) if id!=self.identifiant]): # vrai si un des défenseurs coupe
                        return self.joue(jeu_longue.carte_min(couleur=couleur_longue))
                    else:
                        if self.maitre_couleur(historique,couleur_longue,self.identifiant): # aucun défenseur ne coupe et le preneur a la meilleur carte
                            return self.joue(jeu_longue.carte_max(couleur=couleur_longue))
                        else:
                            return self.joue(jeu_longue.carte_min(couleur=couleur_longue))
                else:
                    if len([carte for carte in possibilitees if carte.couleur not in COULEURS if carte.valeur!=1])!=0: # il lui reste un autre atout que le 1 
                        return self.joue(Jeu([carte for carte in possibilitees if carte.valeur!=1]).carte_min("atout"))
                    else:
                        return self.joue(Jeu(possibilitees).carte_min("atout")) # jete le 1
            else: # défenseurs
                coupe_preneur=self.joueur_coupe(historique,self.preneur)
                cartes_couleur=[Jeu(possibilitees).chercher_cartes(couleur=c) for c in COULEURS]
                cartes_couleur_non_habillees=[Jeu(possibilitees).chercher_cartes(couleur=c, valeur=[i+1 for i in range (10)]) for c in COULEURS]
                roi=[Jeu(possibilitees).chercher_cartes(couleur=c, valeur=14) for c in COULEURS]
                nous_maitre=[self.maitre_couleur(historique,c,self.identifiant) for c in COULEURS]
                atouts=Jeu(possibilitees).chercher_cartes(couleur="atout")
                petit=Jeu(possibilitees).chercher_cartes(couleur="atout",valeur="1")

                condition_1=[coupe_preneur[i]*(len(cartes_couleur_non_habillees[i])!=0) for i in range(len(COULEURS))] # vrai si le preneur coupe et que j'ai des cartes non habillées de cette couleur
                condition_2=[(len(cartes_couleur_non_habillees[i])!=0)*(1-(len(roi[i])!=0)) for i in range(len(COULEURS))] # vrai si le défenseur a des petites cartes dans une couleur ou il n'a pas le roi
                condition_3=[(len(cartes_couleur[i])!=0)*nous_maitre[i]*(1-coupe_preneur[i]) for i in range(len(COULEURS))] # vrai si le preneur ne coupe pas et qu'on est maitre
                
                if OU_logique(condition_1):
                    id_couleur=condition_1.index(max(condition_1))
                    return self.joue(Jeu(cartes_couleur_non_habillees[id_couleur]).carte_min())
                elif OU_logique(condition_2):
                    id_couleur=condition_2.index(max(condition_2))
                    return self.joue(Jeu(cartes_couleur[id_couleur]).carte_min())
                elif OU_logique(condition_3):
                    id_couleur=condition_3.index(max(condition_3))
                    return self.joue(Jeu(cartes_couleur[id_couleur]).carte_max())
                elif len(atouts)-len(petit)!=0: # au moins un atout autre que le petit
                    return self.joue(Jeu(atouts).carte_min())
                elif SOMME([len(i) for i in cartes_couleur])>0:
                    return self.joue(Jeu(possibilitees).carte_min())
                else:
                    return self.joue(petit)
                      
        elif len(cartes_jouees)+1 in [2,3]: # deuxième ou troisième joueur
            #  prendre en compte le fait qu'on peut deja savoir si on va gagner le pli et mettre la carte avec la plus grande valeur

            if cartes_jouees[0].couleur in COULEURS and len([carte for carte in possibilitees if carte.couleur==cartes_jouees[0].couleur])!=0: # une couleur est demandée et on a la couleur
                if self.maitre_couleur(historique,cartes_jouees[0].couleur,self.identifiant)==True: # on est maitre à la couleur demandée
                    return self.joue(Jeu(possibilitees).carte_max(cartes_jouees[0].couleur))
                else:
                    return self.joue(Jeu(possibilitees).carte_min(cartes_jouees[0].couleur))
            
            if len([carte for carte in possibilitees if carte.couleur not in COULEURS])!=0: # on a des atouts               
                val_min=Jeu(cartes_jouees).carte_max("atout")
                if val_min==None:
                    val_min=-1
                else:
                    val_min=val_min.valeur
                atouts_sup=[carte for carte in possibilitees if carte.valeur>val_min and carte.couleur not in COULEURS]

                if len(atouts_sup)>0:
                    return self.joue(Jeu(atouts_sup).carte_min("atout"))
                else:
                    if len([carte for carte in possibilitees if carte.couleur not in COULEURS if carte.valeur!=1])!=0: # il lui reste un autre atout que le 1 
                        return self.joue(Jeu([carte for carte in possibilitees if carte.valeur!=1]).carte_min("atout"))
                    else:
                        return self.joue(Jeu(possibilitees).carte_min("atout")) # jete le 1 
            else:
                carte_p=[[carte for carte in possibilitees if carte.couleur==c if carte.valeur<=10] for c in COULEURS] # trie les petites cartes par couleur

                if OU_logique([len(carte_p)!=0]): # on a une couleur avec des petites cartes
                    # cherche l'indice des couleurs sans habillés
                    couleur_possibles=[i for i in range (len(COULEURS)) if len(carte_p[i])!=0]
                else: # il ne nous reste que des habillés
                    couleur_possibles=[]
                    p=11
                    while len(couleur_possibles)==0 and p<15:
                        couleur_habilles=[[carte for carte in possibilitees if carte.couleur==c if carte.valeur==p] for c in COULEURS] # trie les habillés par couleur
                        p+=1
                        couleur_possibles=[i for i in range (len(COULEURS)) if len(couleur_habilles[i])!=0]
                
                # liste des adversaires
                if self.preneur==self.identifiant:
                    adversaires=[i for i in range (4) if i!=self.identifiant]
                else:
                    adversaires=[self.preneur]
                
                # cherche dans quelle couleur le maximum d'adversaire coupe
                nb_coupe_adv=[SOMME([self.joueur_coupe(historique,i)[j] for i in adversaires]) for j in couleur_possibles]
                if OU_logique([nb_coupe_adv]): #qqu coupe
                    couleur_jouee=COULEURS[couleur_possibles[nb_coupe_adv.index(max(nb_coupe_adv))]]
                    return self.joue(Jeu(possibilitees).carte_min(couleur_jouee))
                else: #personne coupe
                    return self.joue(Jeu(possibilitees).carte_min())

        elif len(cartes_jouees)+1 in [4]: # dernier joueur
            atout_jouees = len([carte for carte in cartes_jouees if carte.couleur == 'atout'])  # Regarde si il y a un atout dans les cartes jouées        
            # Le joueur est preneur
            if self.identifiant==self.preneur or (Jeu(cartes_jouees).maitre()==self.preneur)*(self.identifiant!=self.preneur): # preneur
                if cartes_jouees[0].couleur in COULEURS and len([carte for carte in possibilitees if carte.couleur==cartes_jouees[0].couleur])!=0: # une couleur est demandée et on a la couleur
                        if self.maitre_couleur(historique,cartes_jouees[0].couleur,self.identifiant)==True: # on est maitre à la couleur demandée
                            return self.joue(Jeu(possibilitees).carte_max(cartes_jouees[0].couleur))
                        else:
                            return self.joue(Jeu(possibilitees).carte_min(cartes_jouees[0].couleur))
                
                # Si le joueur coupe et une couleur est demandée
                elif len([carte for carte in possibilitees if carte.couleur not in COULEURS])!=0: # on a des atouts
                    val_min=Jeu(cartes_jouees).carte_max("atout")
                    if val_min==None:
                        val_min=-1
                    else:
                        val_min=val_min.valeur
                    atouts_sup=[carte for carte in possibilitees if carte.valeur>val_min and carte.couleur not in COULEURS]

                    if len(atouts_sup)>0:
                        return self.joue(Jeu(atouts_sup).carte_min("atout"))
                    else:
                        if len([carte for carte in possibilitees if carte.couleur not in COULEURS if carte.valeur!=1])!=0: # il lui reste un autre atout que le 1 
                            return self.joue(Jeu([carte for carte in possibilitees if carte.valeur!=1]).carte_min("atout"))
                        else:
                            return self.joue(Jeu(possibilitees).carte_min("atout")) # jete le 1                            

                # on défausse (une petite carte)
                else:
                    return self.joue(Jeu(possibilitees).carte_min())
                  
            
            else: # le joueur est défenseur et ils gagnent (on veut maximiser les points)
                if cartes_jouees[0].couleur in COULEURS and len([carte for carte in possibilitees if carte.couleur==cartes_jouees[0].couleur])!=0: # une couleur est demandée et on a la couleur
                    return self.joue(Jeu(possibilitees).carte_max(cartes_jouees[0].couleur))
                
                # Si le joueur coupe et une couleur est demandée
                elif len([carte for carte in possibilitees if carte.couleur not in COULEURS])!=0: # on a des atouts
                    val_min=Jeu(cartes_jouees).carte_max("atout")
                    if val_min==None:
                        val_min=-1
                    else:
                        val_min=val_min.valeur
                    atouts_sup=[carte for carte in possibilitees if carte.valeur>val_min and carte.couleur not in COULEURS]

                    if len(atouts_sup)>0:
                        return self.joue(Jeu(atouts_sup).carte_min("atout"))
                    else:
                        return self.joue(Jeu(possibilitees).carte_min("atout"))
                    
                # on défausse (une grosse carte)
                else:
                    return self.joue(Jeu(possibilitees).carte_max())
                            
        # if False: # dernier joueur
        #     # liste des adversaires
        #     if self.preneur==self.identifiant:
        #         adversaires=[i for i in range (4) if i!=self.identifiant]
        #     else:
        #         adversaires=[self.preneur]
            
        #     # si on est en train de gagner
        #     if (Jeu(cartes_jouees).maitre()+historique.dernier_gagnant())%4 not in adversaires:
        #         # suite a revoir j'ai pas compris le graphe
        #         pass
        #     return                
    
    def choix_chien(self,chien:Jeu): # le joueur fait son chien
        jeu=Jeu(self.jeu.cartes+chien.cartes)
        nv_chien=[]

        compte_couleur=[len(jeu.chercher_cartes(couleur=i)) for i in COULEURS]
        compte_roi=[len(jeu.chercher_cartes(valeur=14,couleur=i)) for i in COULEURS]

        # Partie 1 : met au chien le max des couleurs min sans roi
        for k in range (len(COULEURS)): # analyse toutes les couleurs
            for j in range (len(COULEURS)): # compare toutes les couleurs
                if compte_couleur[j]==min(compte_couleur) and compte_roi[j]==0:
                    i=13
                    while len(nv_chien)<6 and i>0:
                        l=jeu.chercher_cartes(valeur=i,couleur=COULEURS[j])
                        if len(l)==1:
                            nv_chien.append(l[0])
                        i-=1
                    compte_couleur[j]=100
        
        # Partie 2 : si on a les 4 rois, met au chien le max des couleurs min sans roi
        for k in range (len(COULEURS)): # analyse toutes les couleurs
            for j in range (len(COULEURS)): # compare toutes les couleurs
                if compte_couleur[j]==min(compte_couleur):
                    i=13
                    while len(nv_chien)<6 and i>0:
                        l=jeu.chercher_cartes(valeur=i,couleur=COULEURS[j])
                        if len(l)==1:
                            nv_chien.append(l[0])
                        i-=1
                    compte_couleur[j]=100
        
        # Partie 3 : si on a 4 rois et pas assez de carte hors atouts
        i=2
        while len(nv_chien)<6:
            l=jeu.chercher_cartes(valeur=i,couleur="atout")
            if len(l)==1:
                nv_chien.append(l[0])
            i+=1
        
        # met les autres cartes dans le jeu du joueur
        l=[]
        self.jeu.cartes=[]

        for carte in jeu.cartes:
            if (carte.valeur,carte.couleur) not in [(c.valeur,c.couleur) for c in nv_chien]:
                self.jeu.cartes.append(carte)

        return Jeu(nv_chien)
    
class IA_0(JOUEUR):
    def __init__(self, jeu, id):
        JOUEUR.__init__(self, jeu, id)

    def evaluation_jeu(self):
        evaluation=0

        # 1 point par atout
        evaluation+=len(self.jeu.chercher_cartes(couleur="atout"))

        # ajoute 2 points supplémentaire pour les bouts
        evaluation+=2*len(self.jeu.chercher_cartes(0,"atout")+self.jeu.chercher_cartes(1,"atout")+self.jeu.chercher_cartes(21,"atout"))

        # ajoute 1 points supplémentaire pour les roi
        evaluation+=len(self.jeu.chercher_cartes(valeur=14, couleur=COULEURS))
        
        # choisit mon annonce en fonction
        evaluation_min=[0,11,14,18,22] # evaluation minimal pour prendre une ANNONCE (attention l'ordre est inversé)

        for i,e in enumerate(evaluation_min):
            if evaluation>=e:
                mon_annonce=ANNONCES[-i-1]
        return mon_annonce
    
    def choix_carte(self,cartes_jouees:list,historique:Historique): # décide quelle carte il va jouer à ce tour
        # cartes jouables
        possibilitees=self.carte_jouable(cartes_jouees)
        # choisit aléatoirement
        carte_jouee=random.choice(possibilitees)
        carte_jouee=self.jeu.supprimer(carte_jouee)
        return carte_jouee
    
    def choix_chien(self,chien:Jeu): # le joueur fait son chien
        jeu=Jeu(self.jeu.cartes+chien.cartes)
        nv_chien=[]

        compte_couleur=[len(jeu.chercher_cartes(couleur=i)) for i in COULEURS]

        # on essaye de faire des coupes
        for i,nb_carte in enumerate(compte_couleur):
            if nb_carte<=6-len(nv_chien):
                for carte in jeu.chercher_cartes(couleur=COULEURS[i]):
                    nv_chien.append(carte)
        
        # on met le reste aléatoire
        for k in range(6-len(nv_chien)):
            possibilitees=jeu.chercher_cartes(couleur=COULEURS,valeur=[i+1 for i in range(13)])
            nv_chien.append(random.choice(possibilitees))
        for k in range(6-len(nv_chien)):
            possibilitees=jeu.chercher_cartes(couleur="atout",valeur=[i+2 for i in range(19)]) # sinon on prend des atouts
            nv_chien.append(random.choice(possibilitees))
        
        # met les autres cartes dans le jeu du joueur
        l=[]
        self.jeu.cartes=[]

        for carte in jeu.cartes:
            if (carte.valeur,carte.couleur) not in [(c.valeur,c.couleur) for c in nv_chien]:
                self.jeu.cartes.append(carte)

        return Jeu(nv_chien)