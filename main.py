from fastapi import FastAPI, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import psycopg2
from database_conn import get_db

app = FastAPI()

# Serve static files (CSS, images, etc.)
app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/images", StaticFiles(directory="static/images"), name="images")


# Load HTML templates
templates = Jinja2Templates(directory="templates")

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Route to show Signup Page
@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# Route to register a new user
@app.post("/register")
def register_user(
    name: str = Form(...),
    email: str = Form(...),
    gender: str = Form(...),
    age_range: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db),
):
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, gender, age_range, password) VALUES (%s, %s, %s, %s, %s);",
            (name, email, gender, age_range, password),
        )
        db.commit()
        cursor.close()
        return {"message": "User registered successfully!"}
    except psycopg2.Error as e:
        return {"error": str(e)}

# Route to show Login Page
@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Route to authenticate user login
@app.post("/login")
def login_user(email: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s;", (email, password))
    user = cursor.fetchone()
    cursor.close()

    if user:
        return {"message": "Login successful!", "user": user}
    else:
        return {"error": "Invalid email or password"}


from fastapi.responses import StreamingResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates
import cv2

templates = Jinja2Templates(directory="templates")


import cv2
import mediapipe as mp
import numpy as np

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

def generate_pushup_frames():
    cap = cv2.VideoCapture(0)

    stage = None
    counter = 0

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Recolor image to RGB
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False

            # Make detection
            results = pose.process(image)

            # Recolor back to BGR
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            try:
                landmarks = results.pose_landmarks.landmark

                # Get coordinates
                shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                            landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                         landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
                wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                         landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]

                # Calculate angle
                angle = calculate_angle(shoulder, elbow, wrist)

                # Visualize angle
                cv2.putText(image, str(round(angle, 2)),
                            tuple(np.multiply(elbow, [640, 480]).astype(int)),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

                # Push-up counter logic
                if angle > 160:
                    stage = "up"
                if angle < 90 and stage == 'up':
                    stage = "down"
                    counter += 1
                    print(f"Push-ups: {counter}")

                # Display counter
                cv2.rectangle(image, (0, 0), (225, 73), (245, 117, 16), -1)
                cv2.putText(image, 'REPS', (15, 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
                cv2.putText(image, str(counter),
                            (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2, cv2.LINE_AA)

                # Display form status
                cv2.putText(image, f'Stage: {stage}', (100, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            except Exception as e:
                print("Tracking error:", e)

            # Render detections
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # Encode and yield frame
            ret, buffer = cv2.imencode('.jpg', image)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)

    if angle > 180.0:
        angle = 360 - angle
    return angle


@app.get("/pushup")
def pushup_page(request: Request):
    return templates.TemplateResponse("pushup.html", {"request": request})

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_pushup_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
