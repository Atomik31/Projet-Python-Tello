import cv2
import socket
import time
import numpy as np

print("=" * 60)
print("    TEST VIDÉO TELLO - DÉTECTION D'OBJETS")
print("=" * 60)

# Charger le modèle YOLO pour la détection d'objets
print("\nChargement du modèle de détection d'objets...")
try:
    # Utiliser YOLOv3
    net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
    
    # Charger les noms des classes
    with open("coco.names", "r") as f:
        classes = [line.strip() for line in f.readlines()]
    
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
    
    # Générer des couleurs aléatoires pour chaque classe
    colors = np.random.uniform(0, 255, size=(len(classes), 3))
    
    print("✓ Modèle YOLO chargé avec succès !")
    print(f"✓ {len(classes)} classes d'objets détectables")
    detection_enabled = True
    
except Exception as e:
    print(f"⚠️  Impossible de charger YOLO: {e}")
    print("⚠️  Le test continuera sans détection d'objets")
    print("\n📥 Pour activer la détection, téléchargez:")
    print("   1. https://pjreddie.com/media/files/yolov3.weights")
    print("   2. https://github.com/pjreddie/darknet/blob/master/cfg/yolov3.cfg")
    print("   3. https://github.com/pjreddie/darknet/blob/master/data/coco.names")
    print("   Placez ces fichiers dans le même dossier que test_video.py\n")
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
    """Détecte les objets dans la frame avec YOLO"""
    if not detection_enabled:
        return frame, []
    
    height, width, channels = frame.shape
    
    # Préparer l'image pour YOLO
    blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)
    
    # Informations de détection
    class_ids = []
    confidences = []
    boxes = []
    
    # Parcourir les détections
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            
            # Filtrer les détections faibles
            if confidence > 0.5:
                # Coordonnées du rectangle
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                
                # Coin supérieur gauche
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)
    
    # Appliquer la suppression des non-maximums pour éliminer les doublons
    indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
    
    detected_objects = []
    
    # Dessiner les rectangles et labels
    if len(indexes) > 0:
        for i in indexes.flatten():
            x, y, w, h = boxes[i]
            label = str(classes[class_ids[i]])
            confidence = confidences[i]
            color = colors[class_ids[i]]
            
            # Dessiner le rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
            
            # Préparer le texte
            text = f"{label}: {confidence:.2f}"
            
            # Fond pour le texte
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(frame, (x, y - text_height - 10), (x + text_width, y), color, -1)
            
            # Écrire le texte
            cv2.putText(frame, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            detected_objects.append({
                'label': label,
                'confidence': confidence,
                'box': (x, y, w, h)
            })
    
    return frame, detected_objects


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
    print("   🎯 Détection d'objets ACTIVE")
else:
    print("   ⚠️  Détection d'objets DÉSACTIVÉE")
print("   Appuyez sur 'q' pour quitter\n")

frame_count = 0
total_detections = 0
last_battery_check = time.time()
current_battery = battery

try:
    while True:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            
            # Redimensionner si nécessaire
            if frame.shape[0] != 720 or frame.shape[1] != 960:
                frame = cv2.resize(frame, (960, 720))
            
            # Détection d'objets (toutes les 3 frames pour les performances)
            detected_objects = []
            if detection_enabled and frame_count % 3 == 0:
                frame, detected_objects = detect_objects(frame)
                
                if detected_objects:
                    total_detections += len(detected_objects)
                    # Afficher dans le terminal
                    print(f"Frame {frame_count}:")
                    for obj in detected_objects:
                        print(f"  🎯 {obj['label']} ({obj['confidence']:.2%})")
            
            # Mettre à jour la batterie toutes les 3 secondes
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
                cv2.putText(frame, f"Objets: {len(detected_objects)}", 
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