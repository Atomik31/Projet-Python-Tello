from djitellopy import Tello
import time

def main():
    tello = Tello()
    try:
        tello.connect()
        print("Batterie:", tello.get_battery(), "%")
        print("Température:", tello.get_temperature(), "°C")

        tello.takeoff()
        time.sleep(0.5)

        # Monter 50 cm à vitesse max
        print("Montée...")
        tello.send_rc_control(0, 0, 100, 0)
        time.sleep(1)
        tello.send_rc_control(0, 0, 0, 0)
        time.sleep(1)

        # Avancer 100 cm à vitesse max
        print("Avance...")
        tello.send_rc_control(0, 100, 0, 0)
        time.sleep(3)
        tello.send_rc_control(0, 0, 0, 0)
        time.sleep(1)

        # Rotation 180° à vitesse max
        print("Rotation...")
        tello.send_rc_control(0, 0, 0, 100)
        time.sleep(2)
        tello.send_rc_control(0, 0, 0, 0)
        time.sleep(1)

        # Avancer 100 cm à vitesse max
        print("Avance...")
        tello.send_rc_control(0, 100, 0, 0)
        time.sleep(3)
        tello.send_rc_control(0, 0, 0, 0)
        time.sleep(1)

        tello.land()
        time.sleep(1)
        
    except Exception as e:
        print("Erreur:", e)
        try:
            tello.land()
        except:
            pass
    finally:
        print("Atterrissage terminé.")
        print("Temps de vol:", tello.get_flight_time(), "secondes")
        print("Température:", tello.get_temperature(), "°C")
        tello.end()

if __name__ == "__main__":
    main()