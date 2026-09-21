import os
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split
from models.tarot_value_mlp import TarotValueMLP


# =====================================================================
# 1. LE DATASET DU TACTICIEN (Avec Camp et Contrat)
# =====================================================================
class TarotValueDataset(Dataset):

  def __init__(self, csv_file):
    print(f"Chargement des données pour le Tacticien depuis {csv_file}...")

    dtypes_opti = {
        "valeur_victoire": np.float32,
        "contrat": np.int8,
        "preneur_relatif": np.int8,
    }
    for i in range(78):
      dtypes_opti[f"S_{i}"] = np.int8
      dtypes_opti[f"Y_{i}"] = np.int8

    colonnes_a_lire = (
        ["valeur_victoire", "contrat", "preneur_relatif"]
        + [f"S_{i}" for i in range(78)]
        + [f"Y_{i}" for i in range(78)]
    )
    self.df = pd.read_csv(csv_file, usecols=colonnes_a_lire, dtype=dtypes_opti)

    S_data = self.df[[f"S_{i}" for i in range(78)]].values
    Y_data = self.df[[f"Y_{i}" for i in range(78)]].values
    self.valeur_victoire = self.df["valeur_victoire"].values
    self.contrats = self.df["contrat"].values.astype(np.int64)
    self.preneurs = self.df["preneur_relatif"].values.astype(np.int64)

    # Mapping des positions absolues de 0 à 7
    self.positions_absolues = np.zeros_like(S_data)
    masque_inconnu = (S_data == 6) | (S_data == 4)
    y_mapped = np.where(Y_data == 3, 7, Y_data + 1)
    self.positions_absolues[masque_inconnu] = y_mapped[masque_inconnu]

    self.positions_absolues[S_data == 5] = 7  # Écart
    self.positions_absolues[S_data == 1] = 4  # Tapis
    self.positions_absolues[S_data == 2] = 5  # Pli Attaque
    self.positions_absolues[S_data == 3] = 6  # Pli Défense

    print(f"✅ Dataset Tacticien prêt : {len(self.df)} états de plateau.")

  def __len__(self):
    return len(self.df)

  def __getitem__(self, idx):
    ids_cartes = torch.arange(78, dtype=torch.long)
    positions = torch.tensor(self.positions_absolues[idx], dtype=torch.long)
    preneur = torch.tensor(self.preneurs[idx], dtype=torch.long)
    contrat = torch.tensor(self.contrats[idx], dtype=torch.long)
    valeur = torch.tensor([self.valeur_victoire[idx]], dtype=torch.float32)

    return ids_cartes, positions, preneur, contrat, valeur


# =====================================================================
# 3. LA BOUCLE D'ENTRAÎNEMENT
# =====================================================================
def train_value_model():
  device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
  print(f"🚀 Démarrage du Tacticien sur : {device}")

  dataset = TarotValueDataset("dataset_tarot_transformer.csv")

  train_size = int(0.9 * len(dataset))
  val_size = len(dataset) - train_size
  train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

  train_loader = DataLoader(
      train_dataset, batch_size=1024, shuffle=True, num_workers=0, pin_memory=True
  )
  val_loader = DataLoader(
      val_dataset, batch_size=2048, shuffle=False, num_workers=0, pin_memory=True
  )

  model = TarotValueMLP(d_model=64).to(device)

  criterion = nn.MSELoss()
  optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
  scheduler = optim.lr_scheduler.ReduceLROnPlateau(
      optimizer, mode="min", factor=0.5, patience=2
  )

  epochs = 20
  meilleure_val_loss = float("inf")

  print("\n⚔️ Entraînement du MLP Tactique ⚔️")
  print("--------------------------------------------------")

  for epoch in range(1, epochs + 1):
    t0 = time.time()

    # --- TRAIN ---
    model.train()
    train_loss = 0.0
    for ids, positions, preneur, contrat, valeurs in train_loader:
      ids, positions, preneur, contrat, valeurs = (
          ids.to(device),
          positions.to(device),
          preneur.to(device),
          contrat.to(device),
          valeurs.to(device),
      )

      optimizer.zero_grad()
      predictions = model(ids, positions, preneur, contrat)
      loss = criterion(predictions, valeurs)
      loss.backward()
      optimizer.step()

      train_loss += loss.item() * ids.size(0)
    train_loss /= len(train_loader.dataset)

    # --- VALIDATION ---
    model.eval()
    val_loss = 0.0
    erreur_moyenne_marge = 0.0

    with torch.no_grad():
      for ids, positions, preneur, contrat, valeurs in val_loader:
        ids, positions, preneur, contrat, valeurs = (
            ids.to(device),
            positions.to(device),
            preneur.to(device),
            contrat.to(device),
            valeurs.to(device),
        )

        predictions = model(ids, positions, preneur, contrat)
        loss = criterion(predictions, valeurs)
        val_loss += loss.item() * ids.size(0)

        # Calcul de l'erreur moyenne en points réels de Tarot (multiplicateur x50)
        erreur_moyenne_marge += (
            torch.abs(predictions - valeurs).sum().item() * 50.0
        )

    val_loss /= len(val_loader.dataset)
    erreur_moyenne_marge /= len(val_loader.dataset)

    scheduler.step(val_loss)
    t_epoch = time.time() - t0

    print(
        f"Époque {epoch:02d} | Temps: {t_epoch:.1f}s | Train MSE: {train_loss:.4f}"
        f" | Val MSE: {val_loss:.4f} | Erreur Marge: ±{erreur_moyenne_marge:.1f}"
        " points"
    )

    if val_loss < meilleure_val_loss:
      meilleure_val_loss = val_loss
      torch.save(model.state_dict(), "tarot_value_mlp.pth")
      print("  🌟 Modèle Tactique sauvegardé !")



train_value_model()