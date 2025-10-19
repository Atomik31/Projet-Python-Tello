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
print("  ESC ou Q = Atterrir et quitter")
print("=" * 60 + "\n")

# Décollage
print("🚁 Décollage en cours...")
send_command('takeoff')
time.sleep(5)

# Monter un peu
print("⬆️  Montée...")
send_command('rc 0 0 25 0', wait_response=False)
time.sleep(2.2)
send_command('rc 0 0 0 0', wait_response=False)

print("✓ Tracking activé !\n")

# Paramètres de tracking
w, h = 360, 240
fbRange = [6200, 6800]
pid = [0.4, 0.4, 0]
pError = 0
running = True

def findFace(img):
    imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Paramètres ajustés pour meilleure détection
    # scaleFactor: 1.1 (au lieu de 1.2) = plus sensible
    # minNeighbors: 4 (au lieu de 8) = moins strict
    faces = faceCascade.detectMultiScale(imgGray, 1.1, 4, minSize=(30, 30))
    
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
    area = info[1]
    x, y = info[0]
    fb = 0
    
    error = x - w // 2
    speed = pid[0] * error + pid[1] * (error - pError)
    speed = int(np.clip(speed, -100, 100))
    
    if area > fbRange[0] and area < fbRange[1]:
        fb = 0
    elif area > fbRange[1]:
        fb = -20
    elif area < fbRange[0] and area != 0:
        fb = 20
    
    if x == 0:
        speed = 0
        error = 0
        print("⚠️  Aucun visage détecté")
    else:
        print(f"👤 Visage: X={x:3}, Aire={area:5}, Rotation={speed:4}, Avant/Arrière={fb:3}")
    
    send_command(f'rc 0 {fb} 0 {speed}', wait_response=False)
    
    return error

try:
    while running:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_small = cv2.resize(frame, (w, h))
            frame_small, info = findFace(frame_small)
            pError = trackFace(info, w, pid, pError)
            
            # Afficher la frame en plus grand
            frame_display = cv2.resize(frame_small, (720, 480))
            
            # Ajouter infos
            cv2.putText(frame_display, "FACE TRACKING", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame_display, f"Batterie: {battery}%", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame_display, "Q ou ESC = Quitter", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("Tello Face Tracking", frame_display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # Q ou ESC
            print("\n⚠️  Sortie...")
            running = False
            break

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE (Ctrl+C)")
    running = False

finally:
    print("🛬 Atterrissage...")
    send_command('rc 0 0 0 0', wait_response=False)
    time.sleep(0.3)
    send_command('land')
    time.sleep(3)
    
    cap.release()
    send_command('streamoff', wait_response=False)
    if command_socket:
        command_socket.close()
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")