# 🚀 Projet MLOps – Segmentation et Prédictions

Ce projet utilise des techniques d'apprentissage non supervisé (**Clustering**) pour segmenter les bénéficiaires, identifier les comportements types et automatiser des stratégies de fidélisation via **n8n**.

---

## 📌 Objectif du projet

L’objectif est de regrouper les **nouveaux bénéficiaires** en clusters distincts (fidèles, à risque, occasionnels) afin d'automatiser des actions marketing ciblées via un workflow n8n.

Prédire si un **nouveau bénéficiaire sera fidèle ou à risque de non-fidélisation**, en utilisant un modèle de Machine Learning, puis d’automatiser les actions métier via un workflow n8n.

---

## 🧠 Modèles de Clustering

Le projet compare et utilise deux approches de clustering :

- **K-Means :** Pour une segmentation basée sur la proximité centroïde (groupes de tailles similaires).
- **DBSCAN :** Pour détecter des groupes de formes arbitraires et identifier les "outliers" (bénéficiaires au comportement atypique).

**Sortie du modèle :**
- `Cluster ID` (ex: 0, 1, 2...) → Représentant un segment spécifique de bénéficiaires.
- `-1` (pour DBSCAN) → Bénéficiaires considérés comme du bruit/anomalies.

---

## 🧠 Modèle Machine classification

- Type : Classification  
- Algorithme : XGBoost (XGBClassifier)  
- Objectif :
  - Prédire la fidélité des **nouveaux bénéficiaires**  
- Sortie du modèle :
  - `1` → Client fidèle  
  - `0` → Client à risque  


## 🔬 Suivi des expérimentations – MLflow

MLflow est utilisé pour suivre et gérer les expérimentations du modèle.

### 🎯 Objectifs

- Comparer plusieurs modèles  
- Suivre les performances  
- Sauvegarder les métriques et paramètres  
- Stocker les modèles entraînés  

### 🎯 Métriques suivies
- **Coefficient de Silhouette :** Pour mesurer la séparation des clusters.
- **Indice de Davies-Bouldin :** Pour évaluer la compacité.
- **Inertie (pour K-Means) :** Utilisation de la méthode du coude (Elbow Method).
- Tracking des runs  
- Logging des métriques :
  - Accuracy  
  - Precision  
  - Recall  
- Logging des paramètres :
  - learning_rate  
  - max_depth  
- Sauvegarde du modèle  

### ▶️ Lancer MLflow

```bash
mlflow ui
```

## . API FastAPI

L’API expose le modèle ML pour effectuer des prédictions.

### ⚙️ Paramètres loggués
- `n_clusters` (K-Means)
- `eps` et `min_samples` (DBSCAN)

---

## ⚙️ Architecture du projet

**Base de données ⮕ FastAPI (Assignation de Cluster) ⮕ n8n ⮕ Alertes & Segmentation CSV**

---

## 🚀 Lancement avec Docker

docker run -d --name n8n ^
-p 5678:5678 ^
-v n8n_data:/home/node/.n8n ^
n8nio/n8n
Dans le navigateur taper
http://localhost:5678/workflows