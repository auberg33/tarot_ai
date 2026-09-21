import torch
import torch.nn as nn


class TarotValueMLP(nn.Module):

  def __init__(self, d_model=64):
    super(TarotValueMLP, self).__init__()

    # Dictionnaires d'Embeddings
    self.carte_embed = nn.Embedding(78, d_model)
    self.position_embed = nn.Embedding(
        8, d_model
    )  # 0=Moi, 1=Gauche, 2=Face, 3=Droite...
    self.preneur_embed = nn.Embedding(
        5, d_model
    )  # 0=Moi, 1=Gauche, 2=Face, 3=Droite
    self.contrat_embed = nn.Embedding(
        10, d_model
    )  # 1=Petite, 2=Garde, 4=Garde Sans...

    self.flatten = nn.Flatten()

    # Le Cerveau Tactique (80 jetons : 78 cartes + Preneur + Contrat)
    self.mlp = nn.Sequential(
        nn.Linear(80 * d_model, 1024),
        nn.Mish(),
        nn.Dropout(0.1),
        nn.Linear(1024, 256),
        nn.Mish(),
        nn.Linear(256, 64),
        nn.Mish(),
        nn.Linear(
            64, 1
        ),  # <-- PAS DE TANH ! Permet de prédire une vraie marge continue !
    )

  def forward(self, ids_cartes, positions, preneur_rel, contrat):
    # 1. Les 78 cartes (identité + position sur le plateau)
    mots_cartes = self.carte_embed(ids_cartes) + self.position_embed(positions)

    # 2. Les 2 jetons de contexte global (Qui attaque ? Quel contrat ?)
    mot_preneur = self.preneur_embed(preneur_rel).unsqueeze(
        1
    )  # (Batch, 1, d_model)
    mot_contrat = self.contrat_embed(contrat).unsqueeze(1)  # (Batch, 1, d_model)

    # 3. Concaténation totale : (Batch, 80, d_model)
    sequence_plateau = torch.cat([mots_cartes, mot_preneur, mot_contrat], dim=1)
    vecteur_plateau = self.flatten(sequence_plateau)

    valeur = self.mlp(vecteur_plateau)
    return valeur