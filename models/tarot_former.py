import torch
import torch.nn as nn


class TarotFormer(nn.Module):
    def __init__(self, d_model=128, nhead=4, num_layers=3):
        super(TarotFormer, self).__init__()
        self.d_model = d_model
        
        # Embeddings (Dictionnaires)
        self.carte_embed = nn.Embedding(78, d_model)
        self.statut_embed = nn.Embedding(7, d_model) # 0 à 6 statuts
        self.joueur_embed = nn.Embedding(5, d_model) # 0 à 4 joueurs
        
        # Le Cœur du Transformer
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead, 
            dim_feedforward=d_model * 4,
            dropout=0.1,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # La Tête de Prédiction (Token Classification)
        # Transforme les 128 neurones de réflexion en 4 probabilités (Gauche, Face, Droite, Cachée)
        self.predicteur_position = nn.Linear(d_model, 4)

    def forward(self, ids_cartes, statuts, joueurs):
        # On additionne les vecteurs pour créer le sens de chaque jeton
        mots_cartes = self.carte_embed(ids_cartes) + \
                      self.statut_embed(statuts) + \
                      self.joueur_embed(joueurs)
        
        # La Réflexion : les cartes "discutent" entre elles
        sequence_reflechie = self.transformer(mots_cartes) # (Batch, 78, d_model)
        
        # La Prédiction : chaque carte donne son avis sur sa propre position
        logits_positions = self.predicteur_position(sequence_reflechie) # (Batch, 78, 4)
        
        return logits_positions