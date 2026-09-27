from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    SUPER_ADMIN = "SUPER_ADMIN"
