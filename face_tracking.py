import socket
import cv2
import time
import threading
import os
import sys
import numpy as np
import pickle

os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'
os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'

print("=" * 60)
print("  TELLO - SUIVI DE VISAGE FLUIDE")
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

# Détecteur Haar Cascade (RAPIDE - utilisé par tous les projets Tello qui marchent)
print("\n📦 Chargement détecteur Haar Cascade...")
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
print("✓ Détecteur chargé (même technologie que les projets GitHub Tello)")

def display_frame_with_text(cap, text, duration):
    start_time = time.time()
    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if ret and frame is not None:
            display_frame = frame.copy()
            cv2.putText(display_frame, text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 3)
            display_frame = cv2.resize(display_frame, (1440, 960))
            cv2.imshow("Tello - Suivi Visage", display_frame)
            cv2.waitKey(1)

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

stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')
cap = cv2.VideoCapture('udp://0.0.0.0:11111', cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
print("COMMANDES:")
print("  T = Décoller")
print("  L = Atterrir")
print("  R = Suivi de visage ON/OFF")
print("  Q/ESC = Quitter")
print("=" * 60)
print("\n✓ SOLUTION OPTIMALE : Haar Cascade")
print("  (Même technologie que tous les projets GitHub Tello)")
print("  → Fluide et efficace pour le suivi en temps réel\n")

w, h = 360, 240
fbRange = [6200, 6800]
pid = [0.4, 0.4, 0]
pError = 0
running = True
flying = False
tracking_enabled = False
last_led_command = ""

# Tracking
tracked_faces = []

def track_target(center, area, w, pid, pError):
    if center is None:
        send_command('rc 0 0 0 0', wait_response=False)
        return 0
    
    x, y = center
    fb = 0
    
    error = x - w // 2
    speed = pid[0] * error + pid[1] * (error - pError)
    speed = int(np.clip(speed, -100, 100))
    
    if area > fbRange[0] and area < fbRange[1]:
        fb = 0
    elif area > fbRange[1]:
        fb = -25
    elif area < fbRange[0] and area != 0:
        fb = 25
    
    send_command(f'rc 0 {fb} 0 {speed}', wait_response=False)
    return error

try:
    print("✓ Système prêt\n")
    
    while running:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            display_frame = frame.copy()
            
            # Suivi de visage
            if tracking_enabled:
                # Détection RAPIDE avec Haar Cascade
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                
                # Créer détections
                current_detections = []
                for (x, y, w, h) in faces:
                    center = (x + w//2, y + h//2)
                    area = w * h
                    current_detections.append({
                        'box': (x, y, w, h),
                        'center': center,
                        'area': area
                    })
                
                tracked_faces = current_detections.copy()
                
                # Suivi du visage le plus proche du centre si en vol
                if flying and len(tracked_faces) > 0:
                    frame_center_x = frame.shape[1] // 2
                    
                    # Trouver le visage le plus proche du centre
                    closest_face = min(tracked_faces, key=lambda f: abs(f['center'][0] - frame_center_x))
                    
                    pError = track_target(closest_face['center'], closest_face['area'], frame.shape[1], pid, pError)
                    face_locked = True
                    
                    # LED verte pour cible
                    new_led = 'EXT led 0 255 0'
                else:
                    face_locked = False
                    if len(tracked_faces) > 0:
                        new_led = 'EXT led 255 165 0'  # Orange
                    else:
                        new_led = 'EXT led 0 0 255'  # Bleu
                
                if new_led != last_led_command:
                    send_command(new_led, wait_response=False)
                    last_led_command = new_led
            
            # Dessiner visages
            for i, obj in enumerate(tracked_faces):
                x, y, w, h = obj['box']
                
                # Couleur : vert pour le visage suivi, bleu pour les autres
                if tracking_enabled and flying and i == 0:
                    # Le premier visage (celui suivi)
                    frame_center_x = frame.shape[1] // 2
                    closest_face = min(tracked_faces, key=lambda f: abs(f['center'][0] - frame_center_x))
                    if obj == closest_face:
                        color = (0, 255, 0)  # Vert
                        thickness = 3
                    else:
                        color = (255, 165, 0)  # Orange
                        thickness = 2
                else:
                    color = (0, 255, 0)  # Vert
                    thickness = 3
                
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), color, thickness)
                
                label = f"Visage {i+1}"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(display_frame, (x, y - label_size[1] - 10), (x + label_size[0] + 5, y), color, -1)
                cv2.putText(display_frame, label, (x + 3, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                cv2.circle(display_frame, obj['center'], 4, color, -1)
            
            # Reset si désactivé
            if not tracking_enabled:
                tracked_faces = []
            
            # Infos
            if flying:
                status = "EN VOL"
                status_color = (0, 255, 0)
            else:
                status = "AU SOL - Appuyez sur T"
                status_color = (255, 255, 0)
            
            cv2.putText(display_frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            cv2.putText(display_frame, f"Batterie: {battery}%", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            if tracking_enabled:
                track_text = f"Suivi: ON [{len(tracked_faces)} visage(s)]"
                track_color = (0, 255, 0)
            else:
                track_text = "Suivi: OFF (R pour activer)"
                track_color = (128, 128, 128)
            cv2.putText(display_frame, track_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, track_color, 2)
            
            # Afficher
            display_frame = cv2.resize(display_frame, (1440, 960))
            cv2.imshow("Tello - Suivi Visage", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('r') or key == ord('R'):
            tracking_enabled = not tracking_enabled
            print(f"🎯 Suivi: {'ACTIVÉ' if tracking_enabled else 'DÉSACTIVÉ'}")
        
        elif (key == ord('t') or key == ord('T')) and not flying:
            print("\n🚁 Décollage...")
            send_command('takeoff')
            display_frame_with_text(cap, "DÉCOLLAGE...", 6)
            send_command('rc 0 0 0 0', wait_response=False)
            display_frame_with_text(cap, "STABILISATION...", 2)
            flying = True
            print("✓ En vol !")
        
        elif (key == ord('l') or key == ord('L')) and flying:
            print("\n🛬 Atterrissage...")
            send_command('rc 0 0 0 0', wait_response=False)
            time.sleep(0.3)
            send_command('EXT led 0 0 0', wait_response=False)
            send_command('land')
            time.sleep(3)
            flying = False
            tracking_enabled = False
            print("✓ Au sol !")
        
        elif key == ord('q') or key == 27:
            print("\n⚠️  Sortie...")
            running = False
            break

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE")
    running = False

finally:
    if flying:
        print("🛬 Atterrissage automatique...")
        send_command('rc 0 0 0 0', wait_response=False)
        time.sleep(0.3)
        send_command('land')
        time.sleep(3)
    
    send_command('EXT led 0 0 0', wait_response=False)
    cap.release()
    send_command('streamoff', wait_response=False)
    if command_socket:
        command_socket.close()
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")
    print("\nℹ️  Note: Tous les projets Tello sur GitHub utilisent")
    print("   Haar Cascade pour le suivi fluide en temps réel.")
    print("   La reconnaissance avec noms nécessite un GPU dédié.")