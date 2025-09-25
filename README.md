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
```

Installer la librairie **djitellopy** :  
```bash
pip install djitellopy
```

---

## 🕹️ Utilisation

1. Allume ton drone Tello et connecte ton ordinateur au Wi-Fi du drone.  
2. Lance le script de contrôle :  
```bash
python main.py
```
3. Suis les instructions à l’écran pour envoyer des commandes.

### Exemple minimal avec `djitellopy`
```python
from djitellopy import Tello
import time

# Créer une instance du drone
tello = Tello()

# Connexion
tello.connect()

# Vérification de la batterie
print(f"Batterie: {tello.get_battery()}%")

# Décollage
tello.takeoff()

# Attendre 5 secondes en vol stationnaire
time.sleep(5)

# Atterrissage
tello.land()
```

---

## 📚 Références utiles
- [djitellopy GitHub](https://github.com/damiafuentes/DJITelloPy)  

---

## ⚠️ Avertissement
Utiliser ce projet à vos propres risques. Assurez-vous de voler dans un environnement sûr, dégagé et conforme à la réglementation locale sur les drones.
