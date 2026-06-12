import os
import anthropic
import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

FAQ_DOCUMENTS = [
    {
        "id": "dept_001",
        "text": "The Cardiology department is located in Block A, Floor 2. Consultations run Monday–Friday 8am–6pm. For urgent cardiac matters outside those hours, go directly to A&E.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "dept_002",
        "text": "Radiology handles X-rays, MRI, CT scans, and ultrasounds. Located in Block B, Ground Floor. Most imaging requires a GP or specialist referral.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "dept_003",
        "text": "Maternity services (antenatal care, labour ward, postnatal care) are in the Maternity Unit, Block C, Floor 1. 24/7 emergency maternity line: 0800-555-1234.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "dept_004",
        "text": "The Oncology department provides cancer diagnosis, chemotherapy, and radiotherapy in the Cancer Centre, Block D. A multidisciplinary team supports every cancer patient.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "dept_005",
        "text": "ENT (Ear, Nose and Throat) covers hearing, balance, and throat conditions. Located in Block A, Floor 3. Audiology clinics run every Tuesday and Thursday.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "dept_006",
        "text": "Neurology is in Block B, Floor 2, and treats conditions including epilepsy, migraines, stroke, and multiple sclerosis. New patient appointments require a GP referral.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "dept_007",
        "text": "Psychiatry and Mental Health services are in the Wellbeing Centre, Block E. Both outpatient and crisis support are available. Self-referral accepted for certain programmes.",
        "metadata": {"category": "departments"},
    },
    {
        "id": "visit_001",
        "text": "General visiting hours are 2pm–4pm and 6pm–8pm daily. ICU and High Dependency wards have restricted visiting — call the ward for specific times. Children under 12 must be accompanied by an adult.",
        "metadata": {"category": "visiting"},
    },
    {
        "id": "visit_002",
        "text": "Visitors are asked to clean hands on entering and leaving the ward, avoid visiting if they have cold, flu, or stomach symptoms, and limit visits to two visitors per patient at a time.",
        "metadata": {"category": "visiting"},
    },
    {
        "id": "parking_001",
        "text": "Parking is available in the multi-storey car park on Hospital Road. Rates: first 30 minutes free, then £2/hour up to a £12 daily maximum. Blue Badge holders park free in designated bays near the main entrance.",
        "metadata": {"category": "parking"},
    },
    {
        "id": "policy_001",
        "text": "To cancel or reschedule an appointment, give at least 24 hours notice. You can cancel via MediAssist, by calling 0800-555-0000, or in writing. Repeated no-shows may result in removal from the waiting list.",
        "metadata": {"category": "appointments"},
    },
    {
        "id": "policy_002",
        "text": "GP consultations can be booked online via MediAssist, by calling your surgery, or in person. Same-day urgent appointments are available — call before 9am. Specialist referrals require a GP letter.",
        "metadata": {"category": "appointments"},
    },
    {
        "id": "policy_003",
        "text": "Follow-up appointments are usually auto-scheduled after procedures and specialist consultations. If you have not received yours within 2 weeks, contact the relevant department directly.",
        "metadata": {"category": "appointments"},
    },
    {
        "id": "rx_001",
        "text": "Repeat prescriptions can be requested through MediAssist (Prescriptions section) or at your GP reception. Allow 48 working hours. Prescriptions can be sent electronically to your chosen pharmacy.",
        "metadata": {"category": "prescriptions"},
    },
    {
        "id": "rx_002",
        "text": "NHS prescription charge is £9.90 per item (2026). Exemptions apply if you are over 60, under 16, in full-time education under 19, pregnant, or on qualifying benefits. Pre-payment certificates (PPCs) are available for regular medication.",
        "metadata": {"category": "prescriptions"},
    },
    {
        "id": "ins_001",
        "text": "City General Hospital accepts all NHS-funded patients. For private consultations we accept BUPA, AXA Health, Vitality, Aviva, and WPA. Bring your insurance membership card and referral letter to your appointment.",
        "metadata": {"category": "insurance"},
    },
    {
        "id": "ins_002",
        "text": "To submit an insurance claim, collect a form from Patient Services or download from the hospital website. Submit completed forms with your invoice to your insurer. Our billing team can help: 0800-555-0002.",
        "metadata": {"category": "insurance"},
    },
    {
        "id": "emergency_001",
        "text": "For life-threatening emergencies, call 999 or go directly to A&E (main hospital entrance, open 24/7). For urgent but non-emergency medical advice, call NHS 111.",
        "metadata": {"category": "emergency"},
    },
    {
        "id": "contacts_001",
        "text": "Hospital main switchboard: 0800-555-0000. Patient enquiries: 0800-555-0001. Billing: 0800-555-0002. Maternity emergency: 0800-555-1234. Chaplaincy and spiritual care: 0800-555-0010.",
        "metadata": {"category": "contacts"},
    },
    {
        "id": "facilities_001",
        "text": "The hospital café is open Monday–Friday 7am–7pm and weekends 8am–5pm (Main Atrium). Free WiFi is available throughout the hospital (network: CityGeneral_Guest).",
        "metadata": {"category": "facilities"},
    },
    {
        "id": "facilities_002",
        "text": "Interpreter services are available for over 100 languages. Request an interpreter when booking or call Patient Services. A phone interpretation service is also available immediately on request.",
        "metadata": {"category": "facilities"},
    },
    {
        "id": "prep_001",
        "text": "For most blood tests, fast (no food or drink except water) for 8–12 hours beforehand. Bring your appointment letter and a list of current medications. Wear loose clothing if a physical examination is planned.",
        "metadata": {"category": "preparation"},
    },
    {
        "id": "prep_002",
        "text": "For MRI scans, remove all metal objects including jewellery and hearing aids. Tell staff if you have a pacemaker, metal implants, or are pregnant. A contrast dye injection may be given — declare any known allergies in advance.",
        "metadata": {"category": "preparation"},
    },
]

collection = None
claude_client = None


@asynccontextmanager
async def lifespan(app):
    global collection, claude_client
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    chroma = chromadb.Client()
    collection = chroma.get_or_create_collection("hospital_faq", embedding_function=ef)
    if collection.count() == 0:
        collection.add(
            ids=[d["id"] for d in FAQ_DOCUMENTS],
            documents=[d["text"] for d in FAQ_DOCUMENTS],
            metadatas=[d["metadata"] for d in FAQ_DOCUMENTS],
        )
    claude_client = anthropic.Anthropic()
    yield


app = FastAPI(title="MediAssist Retrieval API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SearchRequest(BaseModel):
    query: str
    n_results: int = 3


class AnswerRequest(BaseModel):
    query: str
    n_results: int = 3


@app.post("/search")
def search(request: SearchRequest):
    results = collection.query(query_texts=[request.query], n_results=request.n_results)
    return {
        "results": [
            {"text": doc, "metadata": meta, "score": round(1 - dist, 4)}
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
    }


@app.post("/answer")
def answer(request: AnswerRequest):
    results = collection.query(query_texts=[request.query], n_results=request.n_results)
    context = "\n\n".join(results["documents"][0])

    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=(
            "You are a helpful hospital information assistant for City General Hospital. "
            "Answer the patient's question using only the provided context. "
            "If the context does not contain enough information, say so clearly. "
            "Be concise, empathetic, and professional."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nPatient question: {request.query}",
            }
        ],
    )

    answer_text = next(
        (block.text for block in response.content if hasattr(block, "text") and block.type == "text"),
        "",
    )
    return {"answer": answer_text, "sources": results["documents"][0]}


@app.get("/health")
def health():
    count = collection.count() if collection else 0
    return {"status": "ok", "documents_indexed": count}
