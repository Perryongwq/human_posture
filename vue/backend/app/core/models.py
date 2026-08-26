# backend/app/models.py
from pydantic import BaseModel


class JWTClaims(BaseModel):
    """
    Parsed JWT payload. Fields match VueAuthService HS256 token structure.
    
    Use as: user: JWTClaims = Depends(get_current_user)
    
    Fields:
        username: AD display name (e.g. "jsmith")
        payroll: Employee payroll ID (e.g. "EMP12345")
        deptcode: Department code (e.g. "IT", "FIN")
    """
    username: str
    payroll: str
    deptcode: str
