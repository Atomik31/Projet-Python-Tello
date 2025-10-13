from djitellopy import Tello
import cv2
import time
import signal
import sys

print("=" * 60)
print("    DJI TELLO - VOL AVEC RETOUR VIDÉO")
print("=" * 60)

# Variable globale pour le drone
drone = None


def emergency_landing(sig, frame):
    """Atterrissage d'urgence lors de Ctrl+C"""
    print("\n\n⚠️  ARRÊT D'URGENCE - ATTERRISSAGE IMMÉDIAT ⚠️\n")
    global drone
    if drone:
        try:
            drone.land()
            print("✓ Drone atterri")
            time.sleep(2)
        except:
            print("✗ Erreur lors de l'atterrissage")
        
        try:
            drone.streamoff()
        except:
            pass
        
        cv2.destroyAllWindows()
    
    print("Programme terminé")
    sys.exit(0)


def main():
    global drone
    
    # Configurer le gestionnaire Ctrl+C
    signal.signal(signal.SIGINT, emergency_landing)
    
    # Créer une instance du drone
    drone = Tello()

    # Connexion
    drone.connect()
    battery = drone.get_battery()
    print(f"\n✓ Connecté - Batterie: {battery}%")
    
    if battery < 15:
        print("⚠️  BATTERIE TROP FAIBLE - Rechargez le drone !")
        return

    # Démarrer le flux vidéo
    print("\nDémarrage du flux vidéo...")
    drone.streamon()
    time.sleep(3)

    try:
        # Décollage
        print("\n" + "=" * 60)
        print("DÉCOLLAGE")
        print("=" * 60)
        print("⚠️  Appuyez sur Ctrl+C à tout moment pour atterrir d'urgence")
        print("⚠️  Ou appuyez sur 'q' dans la fenêtre vidéo\n")
        
        drone.takeoff()
        print("✓ Drone en vol !")
        time.sleep(2)

        # Vol avec affichage vidéo continu
        print("\n" + "=" * 60)
        print("VOL EN COURS")
        print("=" * 60 + "\n")
        
        # Montée
        print("→ Montée de 20 cm...")
        drone.move_up(20)
        display_video(drone, 2)
        
        # Rotation
        print("→ Rotation 180°...")
        drone.rotate_clockwise(180)
        display_video(drone, 2)
        
        # Avance
        print("→ Avance 50 cm...")
        drone.move_forward(50)
        display_video(drone, 3)

        # Retour
        print("→ Retour 50 cm...")
        drone.move_back(50)
        display_video(drone, 2)
        
        # Rotation retour
        print("→ Rotation retour 180°...")
        drone.rotate_counter_clockwise(180)
        display_video(drone, 2)
        
        # Descente
        print("→ Descente 20 cm...")
        drone.move_down(20)
        display_video(drone, 2)

    except KeyboardInterrupt:
        # Géré par emergency_landing
        pass
        
    except Exception as e:
        print(f"\n✗ Erreur: {e}")

    finally:
        # Atterrissage normal
        print("\n" + "=" * 60)
        print("ATTERRISSAGE")
        print("=" * 60)
        try:
            drone.land()
            print("✓ Drone atterri")
            time.sleep(3)
        except Exception as e:
            print(f"✗ Erreur atterrissage: {e}")
        
        # Arrêter le flux vidéo
        try:
            drone.streamoff()
        except:
            pass
        
        cv2.destroyAllWindows()
        print("\n✓ Vol terminé !")


def display_video(drone, duration):
    """Affiche la vidéo avec infos en temps réel"""
    start_time = time.time()
    frame_read = drone.get_frame_read()
    
    while time.time() - start_time < duration:
        try:
            frame = frame_read.frame
            
            if frame is None or frame.size == 0:
                continue
            
            # Redimensionner si nécessaire
            if frame.shape[0] != 720 or frame.shape[1] != 960:
                frame = cv2.resize(frame, (960, 720))
            
            # Récupérer infos
            battery = drone.get_battery()
            
            # Couleur batterie
            if battery > 50:
                color = (0, 255, 0)
            elif battery > 20:
                color = (0, 165, 255)
            else:
                color = (0, 0, 255)
            
            # Fond pour texte
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (450, 160), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            # Afficher infos
            cv2.putText(frame, f"Batterie: {battery}%", 
                       (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
            
            try:
                height = drone.get_height()
                cv2.putText(frame, f"Altitude: {height} cm", 
                           (15, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            except:
                pass
            
            try:
                flight_time = drone.get_flight_time()
                cv2.putText(frame, f"Temps: {flight_time}s", 
                           (15, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            except:
                pass
            
            # Instructions
            cv2.putText(frame, "Ctrl+C = Urgence | q = Quitter", 
                       (15, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            cv2.imshow("Tello Camera", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                raise KeyboardInterrupt
                
        except KeyboardInterrupt:
            raise
        except:
            pass
        
        time.sleep(0.01)


if __name__ == "__main__":
    print("\n⚠️  SÉCURITÉ : Ctrl+C = Atterrissage d'urgence immédiat\n")
    main()