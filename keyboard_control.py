import socket
import cv2
import time

print("=" * 60)
print("  CONTRÔLE MANUEL DJI TELLO - CLAVIER")
print("=" * 60)

def send_command(command, tello_address=('192.168.10.1', 8889)):
    """Envoie une commande au Tello"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 9000))
    sock.sendto(command.encode('utf-8'), tello_address)
    
    try:
        response, _ = sock.recvfrom(1024)
        sock.close()
        return response.decode('utf-8').strip()
    except:
        sock.close()
        return None

# Connexion
print("\n1. Connexion au Tello...")
response = send_command('command')
print(f"   Réponse: {response}")

battery = send_command('battery?')
print(f"\n2. Batterie: {battery}%")

print("\n3. Démarrage du flux vidéo...")
send_command('streamoff')
time.sleep(1)
send_command('streamon')
time.sleep(3)

print("\n4. Ouverture du flux...")
cap = cv2.VideoCapture('udp://0.0.0.0:11111', cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Attendre le flux
print("   Attente du flux vidéo...")
for i in range(30):
    ret, frame = cap.read()
    if ret and frame is not None:
        print("   ✓ Flux vidéo OK !")
        break
    time.sleep(0.2)

print("\n" + "=" * 60)
print("COMMANDES CLAVIER :")
print("  ESPACE    = Décoller")
print("  L         = Atterrir")
print("  ↑         = Avancer")
print("  ↓         = Reculer")
print("  ←         = Aller à gauche")
print("  →         = Aller à droite")
print("  W         = Monter")
print("  S         = Descendre")
print("  A         = Rotation gauche")
print("  D         = Rotation droite")
print("  Q         = QUITTER")
print("=" * 60 + "\n")

# Variables de contrôle
speed = 50  # Vitesse de déplacement
flying = False
left_right_velocity = 0
for_back_velocity = 0
up_down_velocity = 0
yaw_velocity = 0

frame_count = 0

try:
    while True:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            
            # Redimensionner
            frame = cv2.resize(frame, (960, 720))
            
            # Récupérer la batterie toutes les 100 frames
            if frame_count % 100 == 0:
                current_battery = send_command('battery?')
            else:
                current_battery = battery
            
            # Couleur batterie
            if int(current_battery) > 50:
                battery_color = (0, 255, 0)
            elif int(current_battery) > 20:
                battery_color = (0, 165, 255)
            else:
                battery_color = (0, 0, 255)
            
            # Fond pour texte
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (450, 200), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            # Afficher les infos
            cv2.putText(frame, f"Batterie: {current_battery}%", 
                       (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, battery_color, 2)
            
            status = "EN VOL" if flying else "AU SOL"
            status_color = (0, 255, 0) if flying else (128, 128, 128)
            cv2.putText(frame, f"Status: {status}", 
                       (15, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            
            # Afficher les vitesses
            cv2.putText(frame, f"Avant/Arriere: {for_back_velocity}", 
                       (15, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Gauche/Droite: {left_right_velocity}", 
                       (15, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Haut/Bas: {up_down_velocity}", 
                       (15, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Rotation: {yaw_velocity}", 
                       (15, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.imshow("Tello - Controle Clavier", frame)
        
        # Lire la touche pressée
        key = cv2.waitKey(1) & 0xFF
        
        # Réinitialiser les vitesses
        left_right_velocity = 0
        for_back_velocity = 0
        up_down_velocity = 0
        yaw_velocity = 0
        
        # ESPACE = Décoller
        if key == ord(' ') and not flying:
            print("🚁 Décollage...")
            send_command('takeoff')
            flying = True
            time.sleep(5)
            print("✓ En vol")
        
        # L = Atterrir
        elif key == ord('l') and flying:
            print("🛬 Atterrissage...")
            send_command('land')
            flying = False
            time.sleep(3)
            print("✓ Au sol")
        
        # Flèche HAUT = Avancer
        elif key == 82:  # Flèche haut
            for_back_velocity = speed
            print(f"→ Avancer ({speed})")
        
        # Flèche BAS = Reculer
        elif key == 84:  # Flèche bas
            for_back_velocity = -speed
            print(f"← Reculer ({speed})")
        
        # Flèche GAUCHE = Aller à gauche
        elif key == 81:  # Flèche gauche
            left_right_velocity = -speed
            print(f"← Gauche ({speed})")
        
        # Flèche DROITE = Aller à droite
        elif key == 83:  # Flèche droite
            left_right_velocity = speed
            print(f"→ Droite ({speed})")
        
        # W = Monter
        elif key == ord('w'):
            up_down_velocity = speed
            print(f"↑ Monter ({speed})")
        
        # S = Descendre
        elif key == ord('s'):
            up_down_velocity = -speed
            print(f"↓ Descendre ({speed})")
        
        # A = Rotation gauche
        elif key == ord('a'):
            yaw_velocity = -speed
            print(f"↺ Rotation gauche ({speed})")
        
        # D = Rotation droite
        elif key == ord('d'):
            yaw_velocity = speed
            print(f"↻ Rotation droite ({speed})")
        
        # Q = Quitter
        elif key == ord('q'):
            print("\n⚠️  Sortie du programme...")
            if flying:
                print("🛬 Atterrissage automatique...")
                send_command('land')
                time.sleep(3)
            break
        
        # Envoyer les commandes RC si en vol
        if flying:
            send_command(f'rc {left_right_velocity} {for_back_velocity} {up_down_velocity} {yaw_velocity}')

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE - CTRL+C")
    if flying:
        print("🛬 Atterrissage d'urgence...")
        send_command('land')
        time.sleep(3)

finally:
    cap.release()
    send_command('streamoff')
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")