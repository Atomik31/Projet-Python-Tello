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
print("  CONTRÔLE TELLO + RECONNAISSANCE D'OBJETS")
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

# Détection simple de visages (pas de YOLO)
print("\n📦 Chargement détecteur de visages...")
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
print("✓ Détecteur chargé")

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
print("  O=Detection ON/OFF")
print("=" * 60 + "\n")

speed = 50
flying = False
taking_off = False
landing = False
frame_count = 0
current_battery = battery
takeoff_start_time = 0
running = True
detection_enabled = False

# Stockage des objets trackés
tracked_objects = []
max_distance_threshold = 100

keys_pressed = {
    'z': False, 's': False,
    'q': False, 'd': False,
    'w': False, 'c': False,
    'a': False, 'e': False
}

def on_press(key):
    global flying, taking_off, landing, takeoff_start_time, running, speed, detection_enabled, tracked_objects
    
    try:
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
        
        elif k == 'o':
            detection_enabled = not detection_enabled
            if not detection_enabled:
                tracked_objects = []  # Reset tracking quand désactivé
            status = "ACTIVÉE" if detection_enabled else "DÉSACTIVÉE"
            print(f"🔍 Détection: {status}")
        
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

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

try:
    print("✓ Système prêt\n")
    
    while running:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            frame = cv2.resize(frame, (960, 720))
            
            # Détection de visages si activée avec tracking continu
            if detection_enabled:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                
                # Créer les nouvelles détections
                current_detections = []
                for (x, y, w, h) in faces:
                    center = (x + w//2, y + h//2)
                    current_detections.append({
                        'box': (x, y, w, h),
                        'center': center,
                        'label': "Visage",
                        'color': (0, 255, 0)
                    })
                
                # Mettre à jour le tracking
                if len(tracked_objects) > 0 and len(current_detections) > 0:
                    matched_indices = []
                    new_tracked = []
                    
                    for tracked in tracked_objects:
                        best_match = None
                        best_distance = float('inf')
                        best_idx = -1
                        
                        for idx, current in enumerate(current_detections):
                            if idx in matched_indices:
                                continue
                            
                            # Calculer la distance entre les centres
                            dx = tracked['center'][0] - current['center'][0]
                            dy = tracked['center'][1] - current['center'][1]
                            distance = (dx*dx + dy*dy) ** 0.5
                            
                            if distance < best_distance and distance < max_distance_threshold:
                                best_distance = distance
                                best_match = current
                                best_idx = idx
                        
                        if best_match:
                            # Mettre à jour l'objet tracké
                            new_tracked.append({
                                'box': best_match['box'],
                                'center': best_match['center'],
                                'label': best_match['label'],
                                'color': best_match['color']
                            })
                            matched_indices.append(best_idx)
                    
                    # Ajouter les nouvelles détections non matchées
                    for idx, current in enumerate(current_detections):
                        if idx not in matched_indices:
                            new_tracked.append(current)
                    
                    tracked_objects = new_tracked
                else:
                    # Pas d'objets trackés ou pas de détections, remplacer
                    tracked_objects = current_detections.copy()
            
            # Dessiner tous les objets trackés (même si détection désactivée temporairement)
            faces_detected = len(tracked_objects)
            for obj in tracked_objects:
                x, y, w, h = obj['box']
                label = obj['label']
                color = obj['color']
                
                # Rectangle épais
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 3)
                
                # Label avec fond
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(frame, (x, y - label_size[1] - 15), (x + label_size[0] + 10, y), color, -1)
                cv2.putText(frame, label, (x + 5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Point central
                cv2.circle(frame, obj['center'], 5, color, -1)
            
            # Réinitialiser si détection désactivée
            if not detection_enabled:
                tracked_objects = []
            
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
            cv2.rectangle(overlay, (5, 5), (300, 180), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            cv2.putText(frame, "CONTROLE + DETECTION", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"Batterie: {current_battery}%", (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, battery_color, 2)
            
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
            
            cv2.putText(frame, f"Status: {status}", (15, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            
            detect_color = (0, 255, 0) if detection_enabled else (128, 128, 128)
            cv2.putText(frame, f"Detection: {'ON' if detection_enabled else 'OFF'} ({faces_detected})", (15, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, detect_color, 2)
            
            cv2.putText(frame, f"Vitesse: {speed}", (15, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
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
            
            cv2.imshow("Tello - Detection", frame)
        
        if (flying or (taking_off and time.time() - takeoff_start_time > 1)) and not landing:
            any_key_pressed = any(keys_pressed.values())
            
            if any_key_pressed:
                send_command(f'rc {left_right_velocity} {for_back_velocity} {up_down_velocity} {yaw_velocity}', wait_response=False)
            else:
                send_command('rc 0 0 0 0', wait_response=False)
        
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