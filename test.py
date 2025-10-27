from djitellopy import Tello
import time
import signal
import sys

print("=" * 60)
print("    DÉCOLLAGE - 5 SECONDES - ATTERRISSAGE")
print("=" * 60)

drone = None

def emergency_landing(sig, frame):
    """Atterrissage d'urgence lors de Ctrl+C"""
    print("\n⚠️  ARRÊT D'URGENCE ⚠️")
    global drone
    if drone:
        try:
            drone.land()
        except:
            pass
    sys.exit(0)

def main():
    global drone
    signal.signal(signal.SIGINT, emergency_landing)
    
    drone = Tello()
    
    print("\nConnexion...")
    drone.connect()
    battery = drone.get_battery()
    print(f"✓ Batterie: {battery}%")
    
    if battery < 20:
        print("⚠️  Batterie trop faible !")
        return
    
    try:
        # Décollage
        print("\n🚁 Décollage...")
        drone.takeoff()
        print("✓ En vol !")
        time.sleep(1)
        
        # 5 secondes de stabilisation avec compensation avant-droite
        print("\n🔄 Stabilisation 5 secondes...")
        start = time.time()
        
        while time.time() - start < 5:
            # Compensation : arrière (-) et gauche (-)
            drone.send_rc_control(-10, -10, 0, 0)
            time.sleep(0.05)  # 20 Hz
            
            # Affichage compte à rebours
            remaining = 3 - int(time.time() - start)
            if remaining > 0 and int(time.time() - start * 10) % 10 == 0:
                print(f"   {remaining}s...")
        
        print("✓ Stabilisation terminée")
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"✗ Erreur: {e}")
    finally:
        # Atterrissage
        print("\n⬇️  Atterrissage...")
        try:
            drone.land()
            print("✓ Atterri")
            time.sleep(1)
        except:
            pass
        
        print("\n✓ Vol terminé !")

if __name__ == "__main__":
    print("\n⚠️  Ctrl+C = Atterrissage d'urgence\n")
    main()