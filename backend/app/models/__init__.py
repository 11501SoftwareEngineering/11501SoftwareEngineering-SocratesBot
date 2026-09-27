from app.core.database import Base

# 新增的 model 都要在這裡 import，Alembic autogenerate 才偵測得到，例如：
# from app.models.user import User

__all__ = ["Base"]
