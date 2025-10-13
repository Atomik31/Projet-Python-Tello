import socket
import cv2
import numpy as np
import time

######################################################################
width = 640
height = 480
deadZone = 100
######################################################################

startCounter = 0
dir = 0

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

# CONNECT TO TELLO
print("=" * 60)
print("  TELLO - SUIVI D'OBJET PAR COULEUR")
print("=" * 60)
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

# ATTENDRE LES PREMIÈRES FRAMES
print("   Attente du flux vidéo (10 secondes)...")
for i in range(50):
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f"   ✓ Flux vidéo OK !")
        break
    time.sleep(0.2)
else:
    print("   ✗ ERREUR : Pas de flux vidéo !")
    print("   → Vérifiez que test_video.py fonctionne d'abord")
    exit(1)

frameWidth = width
frameHeight = height

# Variables HSV par défaut (jaune/vert)
h_min, h_max = 20, 40
s_min, s_max = 148, 255
v_min, v_max = 89, 255
threshold1, threshold2 = 166, 171
areaMin = 1750

print("\n5. Création des fenêtres de contrôle...")

def empty(a):
    pass

# Créer la fenêtre principale d'abord
dummy = np.zeros((100, 640, 3), dtype=np.uint8)
cv2.imshow('Tello Object Tracking', dummy)
cv2.waitKey(1)

# Puis les fenêtres de trackbar
cv2.namedWindow("HSV")
cv2.createTrackbar("HUE Min", "HSV", h_min, 179, empty)
cv2.createTrackbar("HUE Max", "HSV", h_max, 179, empty)
cv2.createTrackbar("SAT Min", "HSV", s_min, 255, empty)
cv2.createTrackbar("SAT Max", "HSV", s_max, 255, empty)
cv2.createTrackbar("VALUE Min", "HSV", v_min, 255, empty)
cv2.createTrackbar("VALUE Max", "HSV", v_max, 255, empty)

cv2.namedWindow("Parameters")
cv2.createTrackbar("Threshold1", "Parameters", threshold1, 255, empty)
cv2.createTrackbar("Threshold2", "Parameters", threshold2, 255, empty)
cv2.createTrackbar("Area", "Parameters", areaMin, 30000, empty)

# Forcer l'affichage
for _ in range(10):
    cv2.waitKey(10)

print("   ✓ Fenêtres créées")
print("\n" + "=" * 60)
print("INSTRUCTIONS :")
print("  - Ajustez les trackbars HSV pour détecter la couleur")
print("  - Ajustez Area pour filtrer les petits objets")
print("  - 'q' pour atterrir et quitter")
print("  - 't' pour décoller manuellement")
print("=" * 60 + "\n")

def stackImages(scale, imgArray):
    rows = len(imgArray)
    cols = len(imgArray[0])
    rowsAvailable = isinstance(imgArray[0], list)
    width = imgArray[0][0].shape[1]
    height = imgArray[0][0].shape[0]
    if rowsAvailable:
        for x in range(0, rows):
            for y in range(0, cols):
                if imgArray[x][y].shape[:2] == imgArray[0][0].shape[:2]:
                    imgArray[x][y] = cv2.resize(imgArray[x][y], (0, 0), None, scale, scale)
                else:
                    imgArray[x][y] = cv2.resize(imgArray[x][y], (imgArray[0][0].shape[1], imgArray[0][0].shape[0]), None, scale, scale)
                if len(imgArray[x][y].shape) == 2: 
                    imgArray[x][y] = cv2.cvtColor(imgArray[x][y], cv2.COLOR_GRAY2BGR)
        imageBlank = np.zeros((height, width, 3), np.uint8)
        hor = [imageBlank]*rows
        for x in range(0, rows):
            hor[x] = np.hstack(imgArray[x])
        ver = np.vstack(hor)
    else:
        for x in range(0, rows):
            if imgArray[x].shape[:2] == imgArray[0].shape[:2]:
                imgArray[x] = cv2.resize(imgArray[x], (0, 0), None, scale, scale)
            else:
                imgArray[x] = cv2.resize(imgArray[x], (imgArray[0].shape[1], imgArray[0].shape[0]), None, scale, scale)
            if len(imgArray[x].shape) == 2: 
                imgArray[x] = cv2.cvtColor(imgArray[x], cv2.COLOR_GRAY2BGR)
        hor = np.hstack(imgArray)
        ver = hor
    return ver

def getContours(img, imgContour):
    global dir
    contours, hierarchy = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    
    dir = 0
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        areaMin = cv2.getTrackbarPos("Area", "Parameters")
        if area > areaMin:
            cv2.drawContours(imgContour, cnt, -1, (255, 0, 255), 7)
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            x, y, w, h = cv2.boundingRect(approx)
            cx = int(x + (w / 2))
            cy = int(y + (h / 2))

            if (cx < int(frameWidth/2) - deadZone):
                cv2.putText(imgContour, " GO LEFT ", (20, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 3)
                cv2.rectangle(imgContour, (0, int(frameHeight/2 - deadZone)), (int(frameWidth/2) - deadZone, int(frameHeight/2) + deadZone), (0, 0, 255), cv2.FILLED)
                dir = 1
            elif (cx > int(frameWidth / 2) + deadZone):
                cv2.putText(imgContour, " GO RIGHT ", (20, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 3)
                cv2.rectangle(imgContour, (int(frameWidth/2 + deadZone), int(frameHeight/2 - deadZone)), (frameWidth, int(frameHeight/2) + deadZone), (0, 0, 255), cv2.FILLED)
                dir = 2
            elif (cy < int(frameHeight / 2) - deadZone):
                cv2.putText(imgContour, " GO UP ", (20, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 3)
                cv2.rectangle(imgContour, (int(frameWidth/2 - deadZone), 0), (int(frameWidth/2 + deadZone), int(frameHeight/2) - deadZone), (0, 0, 255), cv2.FILLED)
                dir = 3
            elif (cy > int(frameHeight / 2) + deadZone):
                cv2.putText(imgContour, " GO DOWN ", (20, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 3)
                cv2.rectangle(imgContour, (int(frameWidth/2 - deadZone), int(frameHeight/2) + deadZone), (int(frameWidth/2 + deadZone), frameHeight), (0, 0, 255), cv2.FILLED)
                dir = 4
            else: 
                dir = 0

            cv2.line(imgContour, (int(frameWidth/2), int(frameHeight/2)), (cx, cy), (0, 0, 255), 3)
            cv2.rectangle(imgContour, (x, y), (x + w, y + h), (0, 255, 0), 5)
            cv2.putText(imgContour, "Points: " + str(len(approx)), (x + w + 20, y + 20), cv2.FONT_HERSHEY_COMPLEX, .7, (0, 255, 0), 2)
            cv2.putText(imgContour, "Area: " + str(int(area)), (x + w + 20, y + 45), cv2.FONT_HERSHEY_COMPLEX, 0.7, (0, 255, 0), 2)

def display(img):
    cv2.line(img, (int(frameWidth/2) - deadZone, 0), (int(frameWidth/2) - deadZone, frameHeight), (255, 255, 0), 3)
    cv2.line(img, (int(frameWidth/2) + deadZone, 0), (int(frameWidth/2) + deadZone, frameHeight), (255, 255, 0), 3)
    cv2.circle(img, (int(frameWidth/2), int(frameHeight/2)), 5, (0, 0, 255), 5)
    cv2.line(img, (0, int(frameHeight / 2) - deadZone), (frameWidth, int(frameHeight / 2) - deadZone), (255, 255, 0), 3)
    cv2.line(img, (0, int(frameHeight / 2) + deadZone), (frameWidth, int(frameHeight / 2) + deadZone), (255, 255, 0), 3)

left_right_velocity = 0
for_back_velocity = 0
up_down_velocity = 0
yaw_velocity = 0

try:
    frame_count = 0
    
    while True:
        ret, myFrame = cap.read()
        
        if not ret or myFrame is None:
            continue
        
        frame_count += 1
            
        img = cv2.resize(myFrame, (width, height))
        imgContour = img.copy()
        imgHsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        h_min = cv2.getTrackbarPos("HUE Min", "HSV")
        h_max = cv2.getTrackbarPos("HUE Max", "HSV")
        s_min = cv2.getTrackbarPos("SAT Min", "HSV")
        s_max = cv2.getTrackbarPos("SAT Max", "HSV")
        v_min = cv2.getTrackbarPos("VALUE Min", "HSV")
        v_max = cv2.getTrackbarPos("VALUE Max", "HSV")

        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(imgHsv, lower, upper)
        result = cv2.bitwise_and(img, img, mask=mask)

        imgBlur = cv2.GaussianBlur(result, (7, 7), 1)
        imgGray = cv2.cvtColor(imgBlur, cv2.COLOR_BGR2GRAY)
        threshold1 = cv2.getTrackbarPos("Threshold1", "Parameters")
        threshold2 = cv2.getTrackbarPos("Threshold2", "Parameters")
        imgCanny = cv2.Canny(imgGray, threshold1, threshold2)
        kernel = np.ones((5, 5))
        imgDil = cv2.dilate(imgCanny, kernel, iterations=1)
        getContours(imgDil, imgContour)
        display(imgContour)

        # Empiler les images
        stack = stackImages(0.7, ([img, result], [imgDil, imgContour]))
        cv2.imshow('Tello Object Tracking', stack)

        key = cv2.waitKey(1) & 0xFF
        
        # Commande de décollage manuel
        if key == ord('t') and startCounter == 0:
            print("\n🚁 Décollage...")
            send_command('takeoff')
            startCounter = 1
            time.sleep(5)
            print("✓ En vol - Suivi activé")

        # Contrôle de vol
        if startCounter > 0:
            if dir == 1:
                yaw_velocity = -60
                left_right_velocity = 0
                for_back_velocity = 0
                up_down_velocity = 0
            elif dir == 2:
                yaw_velocity = 60
                left_right_velocity = 0
                for_back_velocity = 0
                up_down_velocity = 0
            elif dir == 3:
                up_down_velocity = 60
                left_right_velocity = 0
                for_back_velocity = 0
                yaw_velocity = 0
            elif dir == 4:
                up_down_velocity = -60
                left_right_velocity = 0
                for_back_velocity = 0
                yaw_velocity = 0
            else:
                left_right_velocity = 0
                for_back_velocity = 0
                up_down_velocity = 0
                yaw_velocity = 0
            
            send_command(f'rc {left_right_velocity} {for_back_velocity} {up_down_velocity} {yaw_velocity}')

        if key == ord('q'):
            print("\n🛬 Atterrissage...")
            send_command('land')
            break

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE")
    send_command('land')

finally:
    cap.release()
    send_command('streamoff')
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")