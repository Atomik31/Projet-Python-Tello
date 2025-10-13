import cv2
import socket
import time
import numpy as np
import urllib.request
import os

print("=" * 60)
print("    TEST VIDÉO TELLO - DÉTECTION D'OBJETS")
print("=" * 60)

# Charger le modèle MobileNet-SSD
print("\nChargement du modèle de détection d'objets...")
try:
    model_file = "mobilenet_iter_73000.caffemodel"
    config_file = "deploy.prototxt"
    
    if not os.path.exists(model_file):
        print("Téléchargement du modèle MobileNet-SSD (23 MB)...")
        urllib.request.urlretrieve(
            "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel",
            model_file
        )
        print("✓ Modèle téléchargé")
    
    if not os.path.exists(config_file):
        print("Téléchargement de la configuration...")
        urllib.request.urlretrieve(
            "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
            config_file
        )
        print("✓ Configuration téléchargée")
    
    net = cv2.dnn.readNetFromCaffe(config_file, model_file)
    
    classes = ["arriere-plan", "avion", "velo", "oiseau", "bateau", "bouteille", "bus",
               "voiture", "chat", "chaise", "vache", "table", "chien", "cheval",
               "moto", "personne", "plante", "mouton", "sofa", "train", "tv"]
    
    colors = np.random.uniform(0, 255, size=(len(classes), 3))
    
    print("✓ Modèle MobileNet-SSD chargé avec succès !")
    print(f"✓ {len(classes)-1} classes d'objets détectables")
    detection_enabled = True
    
except Exception as e:
    print(f"⚠️  Erreur lors du chargement du modèle: {e}")
    detection_enabled = False


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


def detect_objects(frame):
    """Détecte les objets dans la frame avec MobileNet-SSD"""
    if not detection_enabled:
        return []
    
    height, width = frame.shape[:2]
    
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()
    
    detected_objects = []
    
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        
        if confidence > 0.5:
            class_id = int(detections[0, 0, i, 1])
            
            x1 = int(detections[0, 0, i, 3] * width)
            y1 = int(detections[0, 0, i, 4] * height)
            x2 = int(detections[0, 0, i, 5] * width)
            y2 = int(detections[0, 0, i, 6] * height)
            
            detected_objects.append({
                'class_id': class_id,
                'label': classes[class_id],
                'confidence': confidence,
                'box': (x1, y1, x2, y2)
            })
    
    return detected_objects


def draw_detections(frame, detected_objects):
    """Dessine les détections sur la frame"""
    for obj in detected_objects:
        x1, y1, x2, y2 = obj['box']
        label = obj['label']
        confidence = obj['confidence']
        color = colors[obj['class_id']]
        
        # Rectangle
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Texte
        text = f"{label}: {confidence:.2f}"
        (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        
        # Fond pour le texte
        cv2.rectangle(frame, (x1, y1 - text_height - 10), (x1 + text_width, y1), color, -1)
        cv2.putText(frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    return frame


# Connexion
print("\n1. Connexion au Tello...")
response = send_command('command')
print(f"   Réponse: {response}")

print("\n2. Batterie...")
battery = send_command('battery?')
print(f"   Batterie: {battery}%")

print("\n3. Démarrage du flux vidéo...")
response = send_command('streamon')
print(f"   Réponse: {response}")
time.sleep(3)

print("\n4. Ouverture du flux avec OpenCV...")
cap = cv2.VideoCapture('udp://0.0.0.0:11111', cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

print("\n5. Affichage vidéo avec détection d'objets...")
if detection_enabled:
    print("   🎯 Détection d'objets ACTIVE (MobileNet-SSD)")
else:
    print("   ⚠️  Détection d'objets DÉSACTIVÉE")
print("   Appuyez sur 'q' pour quitter\n")

frame_count = 0
total_detections = 0
last_battery_check = time.time()
current_battery = battery

# Variables pour garder les détections affichées
last_detected_objects = []
detection_interval = 5  # Détecter toutes les 5 frames
frames_since_detection = 0

try:
    while True:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            
            # Redimensionner
            if frame.shape[0] != 720 or frame.shape[1] != 960:
                frame = cv2.resize(frame, (960, 720))
            
            # Détecter les objets toutes les N frames
            if detection_enabled and frames_since_detection >= detection_interval:
                detected_objects = detect_objects(frame)
                
                if detected_objects:
                    last_detected_objects = detected_objects
                    total_detections += len(detected_objects)
                    
                    # Afficher dans le terminal
                    print(f"Frame {frame_count}:")
                    for obj in detected_objects:
                        print(f"  🎯 {obj['label']} ({obj['confidence']:.2%})")
                
                frames_since_detection = 0
            else:
                frames_since_detection += 1
            
            # Toujours dessiner les dernières détections
            if last_detected_objects:
                frame = draw_detections(frame, last_detected_objects)
            
            # Mettre à jour la batterie
            if time.time() - last_battery_check > 3:
                current_battery = send_command('battery?')
                last_battery_check = time.time()
            
            # Couleur batterie
            if int(current_battery) > 50:
                battery_color = (0, 255, 0)
            elif int(current_battery) > 20:
                battery_color = (0, 165, 255)
            else:
                battery_color = (0, 0, 255)
            
            # Fond pour texte
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (400, 160), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            # Texte infos
            cv2.putText(frame, f"Frame: {frame_count}", 
                       (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"Batterie: {current_battery}%", 
                       (15, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, battery_color, 2)
            
            # Statut détection
            if detection_enabled:
                cv2.putText(frame, f"Objets: {len(last_detected_objects)}", 
                           (15, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame, f"Total: {total_detections}", 
                           (15, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            else:
                cv2.putText(frame, "Detection: OFF", 
                           (15, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 128, 128), 2)
            
            cv2.imshow("Tello - Detection d'objets ('q' pour quitter)", frame)
            
            if frame_count == 1:
                print("✓ PREMIÈRE FRAME AFFICHÉE !")
            
            if frame_count % 100 == 0:
                print(f"✓ {frame_count} frames affichées")
        else:
            print("⚠️  Pas de frame reçue")
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("\n⚠️ Arrêt par Ctrl+C")

finally:
    print("\n6. Arrêt...")
    cap.release()
    cv2.destroyAllWindows()
    send_command('streamoff')
    
    print("\n" + "=" * 60)
    print(f"✓ Test terminé")
    print(f"  - {frame_count} frames affichées")
    if detection_enabled:
        print(f"  - {total_detections} objets détectés au total")
    print("=" * 60)