import cv2
import numpy as np
import socket
import threading
import time
import os
import sys

# Masquer les messages d'erreur FFmpeg
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'
os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'

print("=" * 60)
print("  TELLO FACE TRACKING AUTOMATIQUE")
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

# Charger le cascade
print("\n📦 Chargement détecteur de visages...")
faceCascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
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

# Restaurer stderr
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
print("FACE TRACKING AUTOMATIQUE")
print("  T = Décoller  L = Atterrir")
print("  ESC ou Q = Quitter")
print("=" * 60 + "\n")

print("🎥 Affichage du flux vidéo...")
print("   Appuyez sur T pour décoller quand vous êtes prêt\n")

# Paramètres de tracking
w, h = 360, 240
fbRange = [6200, 6800]
# PID plus agressif pour meilleure réactivité
pid = [0.6, 0.6, 0]
pError = 0
running = True
flying = False
face_locked = False
blink_state = False
last_blink_time = time.time()
last_led_command = ""

def findFace(img):
    imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Paramètres ajustés pour meilleure détection
    # scaleFactor: 1.1 = plus sensible
    # minNeighbors: 3 = détection plus rapide et réactive
    faces = faceCascade.detectMultiScale(imgGray, 1.1, 3, minSize=(30, 30))
    
    myFaceListC = []
    myFaceListArea = []
    
    for (x, y, w, h) in faces:
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cx = x + w // 2
        cy = y + h // 2
        area = w * h
        cv2.circle(img, (cx, cy), 5, (0, 255, 0), cv2.FILLED)
        myFaceListC.append([cx, cy])
        myFaceListArea.append(area)
    
    if len(myFaceListArea) != 0:
        i = myFaceListArea.index(max(myFaceListArea))
        return img, [myFaceListC[i], myFaceListArea[i]]
    else:
        return img, [[0, 0], 0]

def trackFace(info, w, pid, pError):
    global face_locked
    area = info[1]
    x, y = info[0]
    fb = 0
    
    error = x - w // 2
    speed = pid[0] * error + pid[1] * (error - pError)
    speed = int(np.clip(speed, -100, 100))
    
    # Zones de distance ajustées pour réaction plus rapide
    if area > fbRange[0] and area < fbRange[1]:
        fb = 0
    elif area > fbRange[1]:
        fb = -25  # Reculer plus vite
    elif area < fbRange[0] and area != 0:
        fb = 25   # Avancer plus vite
    
    if x == 0:
        speed = 0
        error = 0
        face_locked = False
        print("⚠️  Aucun visage détecté")
    else:
        face_locked = True
        print(f"👤 Visage: X={x:3}, Aire={area:5}, Rotation={speed:4}, Avant/Arrière={fb:3}")
    
    send_command(f'rc 0 {fb} 0 {speed}', wait_response=False)
    
    return error

try:
    # Afficher d'abord le flux vidéo
    frame_count = 0
    
    while running:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            frame_small = cv2.resize(frame, (w, h))
            
            # Si le drone vole, faire le tracking
            if flying:
                frame_small, info = findFace(frame_small)
                pError = trackFace(info, w, pid, pError)
                
                # Gestion des LEDs selon l'état
                current_time = time.time()
                
                if face_locked:
                    # VERT = Visage détecté et suivi
                    new_led_command = 'EXT led 0 255 0'
                    if new_led_command != last_led_command:
                        send_command(new_led_command, wait_response=False)
                        last_led_command = new_led_command
                else:
                    # BLEU clignotant = Recherche de visage
                    if current_time - last_blink_time > 0.5:
                        blink_state = not blink_state
                        last_blink_time = current_time
                        
                        if blink_state:
                            new_led_command = 'EXT led 0 0 255'
                        else:
                            new_led_command = 'EXT led 0 0 0'
                        
                        if new_led_command != last_led_command:
                            send_command(new_led_command, wait_response=False)
                            last_led_command = new_led_command
            
            # Afficher la frame en taille réduite (1440x960 au lieu de 2160x1440)
            frame_display = cv2.resize(frame_small, (1440, 960))
            
            # Ajouter infos
            if flying:
                cv2.putText(frame_display, "FACE TRACKING - EN VOL", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            else:
                cv2.putText(frame_display, "PRET - Appuyez sur T", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.putText(frame_display, f"Batterie: {battery}%", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Afficher statut LED seulement si en vol
            if flying:
                if face_locked:
                    led_status = "LED: VERT (Visage suivi)"
                    led_color = (0, 255, 0)
                else:
                    led_status = "LED: BLEU (Recherche...)"
                    led_color = (255, 100, 0)
                cv2.putText(frame_display, led_status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, led_color, 2)
            
            cv2.putText(frame_display, "T=Decoller  L=Atterrir  Q/ESC=Quitter", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("Tello Face Tracking", frame_display)
        
        key = cv2.waitKey(1) & 0xFF
        
        # Touche T pour décoller
        if (key == ord('t') or key == ord('T')) and not flying:
            print("\n🚁 Décollage en cours...")
            send_command('takeoff')
            time.sleep(5)
            
            print("⬆️  Montée...")
            send_command('rc 0 0 25 0', wait_response=False)
            time.sleep(2.2)
            send_command('rc 0 0 0 0', wait_response=False)
            
            flying = True
            print("✓ Tracking activé !\n")
        
        # Touche L pour atterrir
        elif (key == ord('l') or key == ord('L')) and flying:
            print("\n🛬 Atterrissage...")
            send_command('rc 0 0 0 0', wait_response=False)
            time.sleep(0.3)
            send_command('EXT led 0 0 0', wait_response=False)
            send_command('land')
            time.sleep(3)
            flying = False
            print("✓ Au sol !")
        
        # Touche Q ou ESC pour quitter
        elif key == ord('q') or key == 27:
            print("\n⚠️  Sortie...")
            running = False
            break

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE (Ctrl+C)")
    running = False

finally:
    if flying:
        print("🛬 Atterrissage automatique...")
        send_command('rc 0 0 0 0', wait_response=False)
        time.sleep(0.3)
        send_command('land')
        time.sleep(3)
    
    # Éteindre la LED
    send_command('EXT led 0 0 0', wait_response=False)
    
    cap.release()
    send_command('streamoff', wait_response=False)
    if command_socket:
        command_socket.close()
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")