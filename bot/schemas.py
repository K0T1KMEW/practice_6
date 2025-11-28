from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ProductBase(BaseModel):
    link: str
    name: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    
    class Config:
        from_attributes = True

class PriceHistoryResponse(BaseModel):
    id: int
    product_id: int
    price: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductWithPricesResponse(ProductResponse):
    price_history: List[PriceHistoryResponse] = []
    current_price: Optional[float] = None
    
    class Config:
        from_attributes = True