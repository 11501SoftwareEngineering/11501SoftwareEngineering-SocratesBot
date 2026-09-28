from app.core.database import Base

# 新增的 model 請在這裡 import 讓 Alembic autogenerate 能偵測到
# 例如:
# from app.models.user import User

__all__ = ["Base"]
