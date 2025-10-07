from pydantic import BaseModel
from datetime import datetime

class ProducaoBase(BaseModel):
    ficha_id: str
    operador: str
    modelo: str
    servico: str
    tamanho: str
    quantidade: int
    valor: float

class ProducaoCreate(ProducaoBase):
    pass

class ProducaoResponse(ProducaoBase):
    id: int
    criado_em: datetime

    class Config:
        orm_mode = True

        # 👇 Adiciona formatação dd-mm-yyyy na saída
        json_encoders = {
            datetime: lambda v: v.strftime("%d-%m-%Y %H:%M:%S")
        }
