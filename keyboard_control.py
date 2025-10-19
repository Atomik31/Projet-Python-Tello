import socket
import cv2
import time
import threading
import os
import sys
from pynput import keyboard

# Masquer les messages d'erreur FFmpeg
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'
os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'

print("=" * 60)
print("  CONTRÔLE MANUEL DJI TELLO - TYPE FPS")
print("=" * 60)

command_socket = None
socket_lock = threading.Lock()

def init_socket():
    global command_socket
    command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    command_socket.bind(('', 9000))
    command_socket.settimeout(2)

def send_command(command, tello_address=('192.168.10.1', 8889), wait_response=True):
    global command_socket
    with socket_lock:
        try:
            command_socket.sendto(command.encode('utf-8'), tello_address)
            if wait_response:
                try:
                    response, _ = command_socket.recvfrom(1024)
                    return response.decode('utf-8').strip()
                except socket.timeout:
                    return None
            return None
        except Exception as e:
            print(f"Erreur: {e}")
            return None

init_socket()

print("\n1. Connexion au Tello...")
response = send_command('command')
print(f"   Réponse: {response}")

battery = send_command('battery?')
print(f"\n2. Batterie: {battery}%")

if not battery:
    print("⚠️  Erreur de connexion")
    exit(1)

print("\n3. Démarrage du flux vidéo...")
send_command('streamoff')
time.sleep(1)
send_command('streamon')
time.sleep(3)

print("\n4. Ouverture du flux...")

# Rediriger stderr pour masquer les erreurs FFmpeg
stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')

cap = cv2.VideoCapture('udp://0.0.0.0:11111', cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Restaurer stderr après l'ouverture
sys.stderr.close()
sys.stderr = stderr_backup

print("   Attente du flux vidéo...")
for i in range(30):
    ret, frame = cap.read()
    if ret and frame is not None:
        print("   ✓ Flux vidéo OK !")
        break
    time.sleep(0.2)

print("\n" + "=" * 60)
print("COMMANDES (TYPE FPS):")
print("  T=Decoller L=Atterrir Z=Avancer S=Reculer")
print("  Q=Gauche D=Droite W=Monter C=Descendre")
print("  A=RotGauche E=RotDroite P=Stop ESC=Quitter")
print("")
print("REGLAGE VITESSE:")
print("  1=Lent(30) 2=Normal(50) 3=Rapide(70) 4=Max(100)")
print("=" * 60 + "\n")

speed = 100
flying = False
taking_off = False
landing = False
frame_count = 0
current_battery = battery
takeoff_start_time = 0
running = True

# Dictionnaire pour maintenir l'état des touches
keys_pressed = {
    'z': False, 's': False,  # Avant/Arrière
    'q': False, 'd': False,  # Gauche/Droite
    'w': False, 'c': False,  # Haut/Bas
    'a': False, 'e': False   # Rotation
}

# Gestionnaire de clavier avec pynput
def on_press(key):
    global flying, taking_off, landing, takeoff_start_time, running, speed
    
    try:
        # Touches de caractères
        k = key.char.lower() if hasattr(key, 'char') and key.char else None
        
        if k == 't' and not flying and not taking_off:
            print("🚁 Décollage en cours...")
            taking_off = True
            takeoff_start_time = time.time()
            threading.Thread(target=lambda: send_command('takeoff'), daemon=True).start()
        
        elif k == 'l' and flying and not landing:
            print("🛬 Atterrissage en cours...")
            landing = True
            
            def land_thread():
                global flying, landing
                send_command('rc 0 0 0 0', wait_response=False)
                time.sleep(0.3)
                send_command('land')
                time.sleep(3)
                flying = False
                landing = False
                print("✓ Au sol !")
            
            threading.Thread(target=land_thread, daemon=True).start()
        
        elif k == 'p':
            for key_name in keys_pressed:
                keys_pressed[key_name] = False
            print("⏸️  STOP")
        
        # Réglage de la vitesse
        elif k == '1':
            speed = 30
            print(f"⚙️  Vitesse: LENTE ({speed})")
        elif k == '2':
            speed = 50
            print(f"⚙️  Vitesse: NORMALE ({speed})")
        elif k == '3':
            speed = 70
            print(f"⚙️  Vitesse: RAPIDE ({speed})")
        elif k == '4':
            speed = 100
            print(f"⚙️  Vitesse: MAXIMUM ({speed})")
        
        # Touches de mouvement
        elif k == 'z':
            keys_pressed['z'] = True
        elif k == 's':
            keys_pressed['s'] = True
        elif k == 'q':
            keys_pressed['q'] = True
        elif k == 'd':
            keys_pressed['d'] = True
        elif k == 'w':
            keys_pressed['w'] = True
        elif k == 'c':
            keys_pressed['c'] = True
        elif k == 'a':
            keys_pressed['a'] = True
        elif k == 'e':
            keys_pressed['e'] = True
    
    except (AttributeError, TypeError):
        # Touches spéciales
        if key == keyboard.Key.esc:
            print("\n⚠️  Sortie...")
            if flying or taking_off:
                print("🛬 Atterrissage automatique...")
                send_command('rc 0 0 0 0', wait_response=False)
                time.sleep(0.3)
                send_command('land')
                time.sleep(3)
            running = False

def on_release(key):
    try:
        k = key.char.lower() if hasattr(key, 'char') and key.char else None
        
        if k == 'z':
            keys_pressed['z'] = False
        elif k == 's':
            keys_pressed['s'] = False
        elif k == 'q':
            keys_pressed['q'] = False
        elif k == 'd':
            keys_pressed['d'] = False
        elif k == 'w':
            keys_pressed['w'] = False
        elif k == 'c':
            keys_pressed['c'] = False
        elif k == 'a':
            keys_pressed['a'] = False
        elif k == 'e':
            keys_pressed['e'] = False
    
    except (AttributeError, TypeError):
        pass

# Démarrer le listener clavier dans un thread
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

try:
    print("✓ Système prêt\n")
    
    while running:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            frame = cv2.resize(frame, (960, 720))
            
            if frame_count % 100 == 0:
                bat = send_command('battery?')
                if bat:
                    current_battery = bat
            
            try:
                battery_int = int(current_battery)
                if battery_int > 50:
                    battery_color = (0, 255, 0)
                elif battery_int > 20:
                    battery_color = (0, 165, 255)
                else:
                    battery_color = (0, 0, 255)
            except:
                battery_color = (255, 255, 255)
            
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (550, 450), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            cv2.putText(frame, "CONTROLE FPS", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, f"Batterie: {current_battery}%", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.0, battery_color, 3)
            
            # Gérer la transition automatique après décollage
            if taking_off and (time.time() - takeoff_start_time > 3):
                flying = True
                taking_off = False
                print("✓ En vol - Contrôle activé !")
            
            if taking_off:
                status, status_color = "DECOLLAGE...", (0, 255, 255)
            elif landing:
                status, status_color = "ATTERRISSAGE...", (0, 255, 255)
            elif flying:
                status, status_color = "EN VOL", (0, 255, 0)
            else:
                status, status_color = "AU SOL", (128, 128, 128)
            
            # Calculer les vélocités selon les touches maintenues
            left_right_velocity = 0
            for_back_velocity = 0
            up_down_velocity = 0
            yaw_velocity = 0
            
            if (flying or (taking_off and time.time() - takeoff_start_time > 1)) and not landing:
                if keys_pressed['z']:
                    for_back_velocity = speed
                if keys_pressed['s']:
                    for_back_velocity = -speed
                if keys_pressed['q']:
                    left_right_velocity = -speed
                if keys_pressed['d']:
                    left_right_velocity = speed
                if keys_pressed['w']:
                    up_down_velocity = speed
                if keys_pressed['c']:
                    up_down_velocity = -speed
                if keys_pressed['a']:
                    yaw_velocity = -speed
                if keys_pressed['e']:
                    yaw_velocity = speed
            
            cv2.putText(frame, f"Status: {status}", (15, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)
            cv2.putText(frame, f"Avant/Arriere: {for_back_velocity:>4}", (15, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Gauche/Droite: {left_right_velocity:>4}", (15, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Haut/Bas:      {up_down_velocity:>4}", (15, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Rotation:      {yaw_velocity:>4}", (15, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.line(frame, (15, 250), (535, 250), (100, 100, 100), 2)
            
            # Affichage de la vitesse actuelle
            if speed <= 30:
                speed_label, speed_bar_color = "LENTE", (100, 100, 255)
            elif speed <= 50:
                speed_label, speed_bar_color = "NORMALE", (0, 255, 255)
            elif speed <= 70:
                speed_label, speed_bar_color = "RAPIDE", (0, 200, 255)
            else:
                speed_label, speed_bar_color = "MAXIMUM", (0, 100, 255)
            
            cv2.putText(frame, f"Vitesse: {speed_label} ({speed})", (15, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.7, speed_bar_color, 2)
            
            # Barre de vitesse visuelle
            bar_width = int((speed / 100) * 520)
            cv2.rectangle(frame, (15, 285), (535, 305), (50, 50, 50), -1)
            cv2.rectangle(frame, (15, 285), (15 + bar_width, 305), speed_bar_color, -1)
            cv2.rectangle(frame, (15, 285), (535, 305), (150, 150, 150), 2)
            
            cv2.line(frame, (15, 315), (535, 315), (100, 100, 100), 2)
            
            y = 340
            cv2.putText(frame, "COMMANDES:", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            y += 30
            cv2.putText(frame, "T=Decoller  L=Atterrir  ESC=Quitter", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            y += 25
            cv2.putText(frame, "ZQSD=Deplacer  W=Monter  C=Descendre", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            y += 25
            cv2.putText(frame, "A=Rotation Gauche  E=Rotation Droite", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            y += 25
            cv2.putText(frame, "P=Stop  1-4=Vitesse", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            
            cv2.imshow("Tello - Controle FPS", frame)
        
        # Envoyer les commandes RC en continu
        if (flying or (taking_off and time.time() - takeoff_start_time > 1)) and not landing:
            send_command(f'rc {left_right_velocity} {for_back_velocity} {up_down_velocity} {yaw_velocity}', wait_response=False)
        
        # Petite pause pour ne pas surcharger
        cv2.waitKey(1)

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE (Ctrl+C)")
    running = False
    if flying or taking_off:
        send_command('rc 0 0 0 0', wait_response=False)
        time.sleep(0.3)
        send_command('land')
        time.sleep(3)

finally:
    running = False
    listener.stop()
    listener.join(timeout=1)
    send_command('rc 0 0 0 0', wait_response=False)
    cap.release()
    send_command('streamoff', wait_response=False)
    if command_socket:
        command_socket.close()
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")