from djitellopy import Tello
import time


def main():
    # Créer une instance du drone
    tello = Tello()

    # Connexion
    tello.connect()
    print(f"Batterie: {tello.get_battery()}%")

    # Démarrer le flux vidéo (optionnel)
    # tello.streamon()

    try:
        # Décollage
        tello.takeoff()

        # Petit vol de démonstration
        tello.move_up(50)     # Monter de 50 cm
        tello.rotate_clockwise(90)  # Rotation de 90°
        tello.move_forward(100)     # Avancer de 1 mètre
        time.sleep(2)

        # Retour à la position initiale
        tello.move_back(100)
        tello.rotate_counter_clockwise(90)
        tello.move_down(50)

    except Exception as e:
        print(f"Erreur: {e}")

    finally:
        # Atterrissage en toute sécurité
        tello.land()
        # Arrêter le flux vidéo si activé
        # tello.streamoff()


if __name__ == "__main__":
    main()
