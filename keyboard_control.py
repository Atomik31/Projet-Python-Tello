from djitellopy import Tello
import time

def main():
    tello = Tello()
    try:
        tello.connect()
        print("Batterie:", tello.get_battery(), "%")

        tello.takeoff()
        time.sleep(2)

        tello.set_speed(100)  # définir la vitesse à 100 cm/s
        time.sleep(2)

        tello.move_up(50)        # monte de 50 cm = 0.5 mètres
        time.sleep(2)

        tello.move_forward(100)   # avance de 1 mètre
        time.sleep(2)

        tello.rotate_clockwise(180)  # rotation de 180°
        time.sleep(2)

        tello.land()
        print("Atterrissage terminé.")
        print("Temps de vol depuis le décollage:", tello.get_flight_time(), "secondes de vol")
        print("Température du drone:", tello.get_temperature(), "°C")
    except Exception as e:
        print("Erreur :", e)
        try:
            tello.land()
        except:
            pass
    finally:
        tello.end()

if __name__ == "__main__":
    main()