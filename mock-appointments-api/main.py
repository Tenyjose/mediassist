from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
import jwt
import os

app = FastAPI(title="MediAssist Mock Appointments API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "mediassist-mock-secret")
JWT_ALGORITHM = "HS256"
security = HTTPBearer()

APPOINTMENTS = [
    {"appointmentId": "APT001", "patientName": "Sarah Johnson", "department": "Cardiology", "doctor": "Dr. Emily Hart", "date": "2026-06-20", "type": "gp_consultation", "isCancelled": False},
    {"appointmentId": "APT002", "patientName": "Michael Chen", "department": "Radiology", "doctor": "Dr. James Obi", "date": "2026-06-21", "type": "specialist_referral", "isCancelled": False},
    {"appointmentId": "APT003", "patientName": "Priya Sharma", "department": "Orthopaedics", "doctor": "Dr. Laura Voss", "date": "2026-06-22", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT004", "patientName": "Daniel Osei", "department": "Neurology", "doctor": "Dr. Marco Ricci", "date": "2026-06-23", "type": "specialist_referral", "isCancelled": False},
    {"appointmentId": "APT005", "patientName": "Amina Diallo", "department": "General Practice", "doctor": "Dr. Sarah Mills", "date": "2026-06-18", "type": "gp_consultation", "isCancelled": True},
    {"appointmentId": "APT006", "patientName": "Carlos Rivera", "department": "Dermatology", "doctor": "Dr. Aisha Patel", "date": "2026-06-24", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT007", "patientName": "Emma Wilson", "department": "Oncology", "doctor": "Dr. Robert Kim", "date": "2026-06-25", "type": "specialist_referral", "isCancelled": False},
    {"appointmentId": "APT008", "patientName": "Ahmed Al-Hassan", "department": "Endocrinology", "doctor": "Dr. Claire Ford", "date": "2026-06-19", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT009", "patientName": "Fatima Nwosu", "department": "Maternity", "doctor": "Dr. Sophie Lang", "date": "2026-06-26", "type": "gp_consultation", "isCancelled": False},
    {"appointmentId": "APT010", "patientName": "Liam O'Brien", "department": "Cardiology", "doctor": "Dr. Emily Hart", "date": "2026-06-27", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT011", "patientName": "Yuki Tanaka", "department": "Psychiatry", "doctor": "Dr. Nathan Cole", "date": "2026-06-28", "type": "specialist_referral", "isCancelled": False},
    {"appointmentId": "APT012", "patientName": "Grace Mensah", "department": "Ophthalmology", "doctor": "Dr. Ivan Petrov", "date": "2026-06-30", "type": "gp_consultation", "isCancelled": False},
    {"appointmentId": "APT013", "patientName": "Omar Khalil", "department": "Urology", "doctor": "Dr. Helen Gray", "date": "2026-07-01", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT014", "patientName": "Isabella Cruz", "department": "General Practice", "doctor": "Dr. Sarah Mills", "date": "2026-07-02", "type": "gp_consultation", "isCancelled": False},
    {"appointmentId": "APT015", "patientName": "Kwame Asante", "department": "Haematology", "doctor": "Dr. Zoe Brennan", "date": "2026-07-03", "type": "specialist_referral", "isCancelled": True},
    {"appointmentId": "APT016", "patientName": "Mei Lin", "department": "Rheumatology", "doctor": "Dr. Thomas Webb", "date": "2026-07-04", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT017", "patientName": "James Okafor", "department": "ENT", "doctor": "Dr. Alice Marsh", "date": "2026-07-05", "type": "gp_consultation", "isCancelled": False},
    {"appointmentId": "APT018", "patientName": "Sophia Andersen", "department": "Gastroenterology", "doctor": "Dr. Paul Nguyen", "date": "2026-07-07", "type": "specialist_referral", "isCancelled": False},
    {"appointmentId": "APT019", "patientName": "Emmanuel Boateng", "department": "Orthopaedics", "doctor": "Dr. Laura Voss", "date": "2026-07-08", "type": "follow_up", "isCancelled": False},
    {"appointmentId": "APT020", "patientName": "Aisha Rahman", "department": "Radiology", "doctor": "Dr. James Obi", "date": "2026-07-09", "type": "specialist_referral", "isCancelled": False},
]

today = str(date.today())


class SendCodeRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class CancelAppointmentRequest(BaseModel):
    appointmentId: str


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.post("/auth/send-code")
def send_code(request: SendCodeRequest):
    return {"success": True, "message": f"OTP sent to {request.email}"}


@app.post("/auth/verify-code")
def verify_code(request: VerifyCodeRequest):
    token = jwt.encode(
        {"email": request.email, "role": "patient"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return {"success": True, "token": token}


@app.get("/appointments")
def get_appointments(upcoming: int = 0, payload: dict = Depends(verify_token)):
    results = [a for a in APPOINTMENTS if not a["isCancelled"]]
    if upcoming:
        results = [a for a in results if a["date"] >= today]
    return {"appointments": results, "count": len(results)}


@app.post("/cancel-appointment")
def cancel_appointment(request: CancelAppointmentRequest, payload: dict = Depends(verify_token)):
    for appt in APPOINTMENTS:
        if appt["appointmentId"] == request.appointmentId:
            if appt["isCancelled"]:
                raise HTTPException(status_code=400, detail="Appointment is already cancelled")
            appt["isCancelled"] = True
            return {"success": True, "message": f"Appointment {request.appointmentId} cancelled successfully"}
    raise HTTPException(status_code=404, detail="Appointment not found")


@app.get("/health")
def health():
    return {"status": "ok"}
