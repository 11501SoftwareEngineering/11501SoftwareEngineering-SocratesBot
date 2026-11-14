from fastapi import APIRouter

from app.api.v1.routes import (
    admin_teachers,
    auth,
    courses,
    health,
    inquiry,
    reports,
    student_sessions,
    summaries,
    topics,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin_teachers.router)
api_router.include_router(courses.router)
api_router.include_router(student_sessions.router)
api_router.include_router(topics.router)
api_router.include_router(inquiry.router)
api_router.include_router(reports.router)
api_router.include_router(summaries.router)
