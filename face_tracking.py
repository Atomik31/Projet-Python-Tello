import socket
import cv2
import time
import threading
import os
import sys
import numpy as np
import pickle

# FIX pour Python 3.13 - Forcer l'import de face_recognition_models
try:
    import face_recognition_models
except ImportError:
    print("Installation de face_recognition_models...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "face_recognition_models"])
    import face_recognition_models

# Maintenant on peut importer face_recognition
import face_recognition

# Masquer les messages d'erreur FFmpeg
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'
os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'

print("=" * 60)
print("  TELLO - RECONNAISSANCE FACIALE AVANCÉE")
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

# Base de données des visages
FACES_DB_FILE = "known_faces.pkl"
known_face_encodings = []
known_face_names = []

# Charger la base de données si elle existe
if os.path.exists(FACES_DB_FILE):
    with open(FACES_DB_FILE, 'rb') as f:
        data = pickle.load(f)
        known_face_encodings = data['encodings']
        known_face_names = data['names']
    print(f"\n✓ Base de données chargée : {len(known_face_names)} personne(s) enregistrée(s)")
    for name in known_face_names:
        print(f"  - {name}")
else:
    print("\n⚠️  Aucune base de données trouvée")

def save_faces_database():
    with open(FACES_DB_FILE, 'wb') as f:
        pickle.dump({
            'encodings': known_face_encodings,
            'names': known_face_names
        }, f)
    print(f"✓ Base de données sauvegardée ({len(known_face_names)} personne(s))")

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
print("MODE RECONNAISSANCE FACIALE")
print("  E = Mode Entraînement (enregistrer un visage)")
print("  T = Décoller  L = Atterrir")
print("  R = Reconnaissance ON/OFF")
print("  D = Supprimer une personne")
print("  Q/ESC = Quitter")
print("=" * 60 + "\n")

# Paramètres
w, h = 360, 240
fbRange = [6200, 6800]
pid = [0.6, 0.6, 0]
pError = 0
running = True
flying = False
recognition_enabled = False
training_mode = False
training_name = ""
training_images = []
target_person = ""  # Personne à suivre
face_locked = False
last_led_command = ""
process_this_frame = True

def recognize_faces(frame):
    global face_locked, target_person
    
    # Redimensionner pour accélérer le traitement
    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    
    # Détecter les visages
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
    
    face_names = []
    face_locked = False
    target_center = None
    target_area = 0
    
    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
        name = "Inconnu"
        confidence = 0
        
        if len(known_face_encodings) > 0:
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            best_match_index = np.argmin(face_distances)
            
            if matches[best_match_index]:
                name = known_face_names[best_match_index]
                confidence = int((1 - face_distances[best_match_index]) * 100)
        
        face_names.append((name, confidence))
        
        # Si c'est la personne cible, calculer position et aire
        if name == target_person:
            face_locked = True
            top, right, bottom, left = face_location
            # Convertir en coordonnées originales
            top *= 2
            right *= 2
            bottom *= 2
            left *= 2
            
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            area = (right - left) * (bottom - top)
            
            target_center = (cx, cy)
            target_area = area
    
    return face_locations, face_names, target_center, target_area

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
            
            # Mode entraînement
            if training_mode:
                cv2.putText(display_frame, f"ENTRAÎNEMENT: {training_name}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(display_frame, f"Photos: {len(training_images)}/5", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(display_frame, "Appuyez sur ESPACE pour capturer", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                
                # Détecter visage pour cadrage
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                
                for (top, right, bottom, left) in face_locations:
                    cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Mode reconnaissance
            elif recognition_enabled and flying:
                # Traiter une frame sur deux pour optimiser
                if process_this_frame:
                    face_locations, face_names, target_center, target_area = recognize_faces(frame)
                    
                    if target_center:
                        pError = track_target(target_center, target_area, frame.shape[1], pid, pError)
                
                process_this_frame = not process_this_frame
                
                # Afficher les résultats
                for (top, right, bottom, left), (name, confidence) in zip(face_locations, face_names):
                    # Ajuster coordonnées
                    top *= 2
                    right *= 2
                    bottom *= 2
                    left *= 2
                    
                    # Couleur selon si c'est la cible
                    if name == target_person:
                        color = (0, 255, 0)  # Vert pour cible
                        thickness = 3
                    elif name == "Inconnu":
                        color = (0, 0, 255)  # Rouge pour inconnu
                        thickness = 2
                    else:
                        color = (255, 0, 0)  # Bleu pour connu non-cible
                        thickness = 2
                    
                    cv2.rectangle(display_frame, (left, top), (right, bottom), color, thickness)
                    
                    # Afficher nom et confiance
                    if name != "Inconnu":
                        text = f"{name} ({confidence}%)"
                    else:
                        text = name
                    
                    cv2.rectangle(display_frame, (left, bottom - 25), (right, bottom), color, -1)
                    cv2.putText(display_frame, text, (left + 6, bottom - 6), 
                               cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
                
                # LED selon état
                if face_locked:
                    new_led = 'EXT led 0 255 0'  # Vert = cible lockée
                elif len(face_names) > 0:
                    new_led = 'EXT led 255 165 0'  # Orange = visage détecté mais pas cible
                else:
                    new_led = 'EXT led 0 0 255'  # Bleu = recherche
                
                if new_led != last_led_command:
                    send_command(new_led, wait_response=False)
                    last_led_command = new_led
            
            # Infos générales
            if not training_mode:
                if flying:
                    status = "EN VOL"
                    status_color = (0, 255, 0)
                else:
                    status = "AU SOL - Appuyez sur T"
                    status_color = (255, 255, 0)
                
                cv2.putText(display_frame, status, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                cv2.putText(display_frame, f"Batterie: {battery}%", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                if recognition_enabled:
                    reco_text = f"Reconnaissance: ON (Cible: {target_person})"
                    reco_color = (0, 255, 0)
                else:
                    reco_text = "Reconnaissance: OFF"
                    reco_color = (128, 128, 128)
                cv2.putText(display_frame, reco_text, (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, reco_color, 2)
            
            # Afficher
            display_frame = cv2.resize(display_frame, (1440, 960))
            cv2.imshow("Tello - Reconnaissance Faciale", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        # Mode Entraînement
        if key == ord('e') or key == ord('E'):
            if not training_mode:
                name = input("\n👤 Entrez le nom de la personne à enregistrer: ")
                if name:
                    training_mode = True
                    training_name = name
                    training_images = []
                    print(f"📸 Mode entraînement activé pour: {name}")
                    print("   Prenez 5 photos de face sous différents angles")
                    print("   Appuyez sur ESPACE pour capturer")
        
        # Capturer photo en mode entraînement
        elif key == 32 and training_mode:  # ESPACE
            if len(training_images) < 5:
                training_images.append(frame.copy())
                print(f"   ✓ Photo {len(training_images)}/5 capturée")
                
                if len(training_images) == 5:
                    print("\n🔄 Traitement des images...")
                    
                    # Extraire les encodages
                    encodings = []
                    for img in training_images:
                        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        face_encodings = face_recognition.face_encodings(rgb)
                        if face_encodings:
                            encodings.append(face_encodings[0])
                    
                    if encodings:
                        # Calculer l'encodage moyen
                        avg_encoding = np.mean(encodings, axis=0)
                        known_face_encodings.append(avg_encoding)
                        known_face_names.append(training_name)
                        save_faces_database()
                        
                        print(f"✓ {training_name} enregistré avec succès !")
                        target_person = training_name
                    else:
                        print("❌ Aucun visage détecté dans les images")
                    
                    training_mode = False
                    training_name = ""
                    training_images = []
        
        # Activer/Désactiver reconnaissance
        elif key == ord('r') or key == ord('R'):
            if len(known_face_encodings) == 0:
                print("⚠️  Aucune personne enregistrée ! Utilisez 'E' pour entraîner")
            else:
                recognition_enabled = not recognition_enabled
                if recognition_enabled and not target_person:
                    # Sélectionner la première personne par défaut
                    target_person = known_face_names[0]
                print(f"🔍 Reconnaissance: {'ACTIVÉE' if recognition_enabled else 'DÉSACTIVÉE'}")
                if recognition_enabled:
                    print(f"   Cible: {target_person}")
        
        # Supprimer une personne
        elif key == ord('d') or key == ord('D'):
            if len(known_face_names) > 0:
                print("\n📋 Personnes enregistrées:")
                for i, name in enumerate(known_face_names):
                    print(f"   {i+1}. {name}")
                try:
                    choice = int(input("Numéro à supprimer (0 pour annuler): "))
                    if 0 < choice <= len(known_face_names):
                        removed = known_face_names.pop(choice - 1)
                        known_face_encodings.pop(choice - 1)
                        save_faces_database()
                        print(f"✓ {removed} supprimé")
                        if target_person == removed:
                            target_person = known_face_names[0] if known_face_names else ""
                except:
                    print("Annulé")
        
        # Décoller
        elif (key == ord('t') or key == ord('T')) and not flying:
            print("\n🚁 Décollage...")
            send_command('takeoff')
            time.sleep(5)
            send_command('rc 0 0 25 0', wait_response=False)
            time.sleep(2.2)
            send_command('rc 0 0 0 0', wait_response=False)
            flying = True
            print("✓ En vol !")
        
        # Atterrir
        elif (key == ord('l') or key == ord('L')) and flying:
            print("\n🛬 Atterrissage...")
            send_command('rc 0 0 0 0', wait_response=False)
            time.sleep(0.3)
            send_command('EXT led 0 0 0', wait_response=False)
            send_command('land')
            time.sleep(3)
            flying = False
            print("✓ Au sol !")
        
        # Quitter
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
    
    send_command('EXT led 0 0 0', wait_response=False)
    cap.release()
    send_command('streamoff', wait_response=False)
    if command_socket:
        command_socket.close()
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")