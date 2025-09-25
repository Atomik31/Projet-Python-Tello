# Tello Drone Controller (Python)

Un projet en **Python** permettant de contrôler un drone **DJI Tello** grâce au SDK officiel.  
Ce dépôt propose une interface simple pour envoyer des commandes au drone, récupérer son état et automatiser des séquences de vol.

---

## 🚀 Fonctionnalités
- Connexion au drone via Wi-Fi  
- Envoi de commandes de vol (décoller, atterrir, avancer, reculer, tourner, etc.)  
- Récupération des informations de télémétrie (batterie, vitesse, hauteur, etc.)  
- Possibilité de créer des scripts d’automatisation pour des vols prédéfinis  

---

## 📦 Installation

Cloner le dépôt :  
```bash
git clone https://github.com/ton-utilisateur/tello-drone-controller.git
cd tello-drone-controller
```

Créer un environnement virtuel et installer les dépendances :  
```bash
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

---

## 🕹️ Utilisation

1. Allume ton drone Tello et connecte ton ordinateur au Wi-Fi du drone.  
2. Lance le script de contrôle :  
```bash
python main.py
```
3. Suis les instructions à l’écran pour envoyer des commandes.

---

## 📚 Références utiles


---

## ⚠️ Avertissement
⚠️ Utiliser ce projet à vos propres risques. Assurez-vous de voler dans un environnement sûr, dégagé et conforme à la réglementation locale sur les drones.
