import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
import time
import os
from torch.utils.data import Dataset, DataLoader, random_split
from models.tarot_former import TarotFormer

# =====================================================================
# 1. LE DATASET
# =====================================================================
# =====================================================================
# 1. LE DATASET (Optimisé pour très grande volumétrie)
# =====================================================================
class TarotDataset(Dataset):
    def __init__(self, csv_file):
        print(f"Chargement des données depuis {csv_file} (Optimisation de la RAM)...")
        
        # --- CORRECTION : Diviser l'utilisation de la RAM par 8 ---
        # On force la lecture en 8-bits pour éviter de faire exploser la mémoire
        dtypes_opti = {'contrat': np.int8, 'preneur_relatif': np.int8}
        for i in range(78):
            dtypes_opti[f'S_{i}'] = np.int8
            dtypes_opti[f'J_{i}'] = np.int8
            dtypes_opti[f'Y_{i}'] = np.int8
            
        self.df = pd.read_csv(csv_file, dtype=dtypes_opti)
        
        # Noms des colonnes
        self.S_cols = [f'S_{i}' for i in range(78)]
        self.J_cols = [f'J_{i}' for i in range(78)]
        self.Y_cols = [f'Y_{i}' for i in range(78)]
        
        # Extraction des matrices en conservant le format ultra-léger (int8)
        self.S_data = self.df[self.S_cols].values
        self.J_data = self.df[self.J_cols].values
        self.Y_data = self.df[self.Y_cols].values
        
        print(f"✅ Dataset chargé en mémoire : {len(self.df)} échantillons.")
        
    def __len__(self):
        return len(self.df)
        
    def __getitem__(self, idx):
        # L'ID des cartes est implicite (de 0 à 77)
        ids_cartes = torch.arange(78, dtype=torch.long)
        
        # On convertit en format PyTorch (int64) uniquement au dernier moment pour le GPU
        statuts = torch.tensor(self.S_data[idx], dtype=torch.long)
        joueurs = torch.tensor(self.J_data[idx], dtype=torch.long)
        y_belief = torch.tensor(self.Y_data[idx], dtype=torch.long)
        
        return ids_cartes, statuts, joueurs, y_belief

# =====================================================================
# 3. LA BOUCLE D'ENTRAÎNEMENT
# =====================================================================
def train_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Démarrage sur le matériel : {device}")
    
    # 1. Chargement des données
    fichier_csv = 'dataset_tarot_transformer.csv'
    if not os.path.exists(fichier_csv):
        print(f"❌ Erreur : Le fichier {fichier_csv} est introuvable. Attendez que le générateur termine.")
        return
        
    dataset = TarotDataset(fichier_csv)
    
    # Split Train/Validation (90% / 10%)
    train_size = int(0.9 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
    
    # Sous Windows, avec un gros dataset en RAM, num_workers doit être à 0 !
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=512, shuffle=False, num_workers=0, pin_memory=True)
    
    # 2. Initialisation du Modèle
    model = TarotFormer(d_model=128, nhead=4, num_layers=3).to(device)
    
    # La fonction de perte (CrossEntropy gère nativement le fait qu'il n'y ait qu'1 seule bonne réponse sur 4)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2, verbose=True)
    
    epochs = 20
    meilleure_val_loss = float('inf')
    
    print("\n⚔️ Début de l'entraînement ⚔️")
    print("--------------------------------------------------")
    
    for epoch in range(1, epochs + 1):
        t0 = time.time()
        
        # --- PHASE D'ENTRAÎNEMENT ---
        model.train()
        train_loss = 0.0
        
        for ids, statuts, joueurs, y_belief in train_loader:
            ids, statuts, joueurs, y_belief = ids.to(device), statuts.to(device), joueurs.to(device), y_belief.to(device)
            
            optimizer.zero_grad()
            logits = model(ids, statuts, joueurs) # Shape: (Batch, 78, 4)
            
            # CrossEntropy attend (Batch*78, 4) et (Batch*78)
            loss = criterion(logits.view(-1, 4), y_belief.view(-1))
            loss.backward()
            
            # Anti-explosion des gradients (très utile pour les Transformers)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            train_loss += loss.item() * ids.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        # --- PHASE DE VALIDATION ---
        model.eval()
        val_loss = 0.0
        correct_inconnus = 0
        total_inconnus = 0
        
        with torch.no_grad():
            for ids, statuts, joueurs, y_belief in val_loader:
                ids, statuts, joueurs, y_belief = ids.to(device), statuts.to(device), joueurs.to(device), y_belief.to(device)
                
                logits = model(ids, statuts, joueurs)
                loss = criterion(logits.view(-1, 4), y_belief.view(-1))
                val_loss += loss.item() * ids.size(0)
                
                # --- CALCUL DE LA PRÉCISION DE DÉDUCTION ---
                # On ne compte les points QUE sur les cartes "Inconnues" (Statut == 6)
                # Le réseau ne doit pas gonfler son score en devinant qu'une carte sur la table est sur la table.
                predictions = torch.argmax(logits, dim=-1) # Le choix final du réseau (0, 1, 2 ou 3)
                
                masque_inconnu = (statuts == 6) # True pour les cartes cachées
                correct_inconnus += ((predictions == y_belief) & masque_inconnu).sum().item()
                total_inconnus += masque_inconnu.sum().item()
                
        val_loss /= len(val_loader.dataset)
        precision = (correct_inconnus / total_inconnus * 100) if total_inconnus > 0 else 0.0
        
        scheduler.step(val_loss)
        
        t_epoch = time.time() - t0
        print(f"Époque {epoch:02d}/{epochs} | Temps: {t_epoch:.1f}s | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Précision Détective: {precision:.1f}%")
        
        # Sauvegarde du meilleur modèle
        if val_loss < meilleure_val_loss:
            meilleure_val_loss = val_loss
            torch.save(model.state_dict(), "tarot_former_belief.pth")
            print("  🌟 Modèle sauvegardé (Nouveau Record !)")

train_model()