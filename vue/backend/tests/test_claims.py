# backend/tests/test_claims.py
"""Tests for JWTClaims model — BE-04."""
from app.core.models import JWTClaims


class TestJWTClaims:
    """BE-04: JWTClaims has correct fields."""
    
    def test_jwtclaims_has_username_field(self):
        """JWTClaims has username field."""
        claims = JWTClaims(username="test", payroll="P001", deptcode="IT")
        assert claims.username == "test"
    
    def test_jwtclaims_has_payroll_field(self):
        """JWTClaims has payroll field."""
        claims = JWTClaims(username="test", payroll="P001", deptcode="IT")
        assert claims.payroll == "P001"
    
    def test_jwtclaims_has_deptcode_field(self):
        """JWTClaims has deptcode field."""
        claims = JWTClaims(username="test", payroll="P001", deptcode="IT")
        assert claims.deptcode == "IT"
