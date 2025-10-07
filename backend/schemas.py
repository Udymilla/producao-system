from datetime import datetime
from pydantic import BaseModel

# 🔹 Classe base — usada para criação e atualização
class ProducaoBase(BaseModel):
    operador: str
    produto: str
    quantidade: int
    valor: float

# 🔹 Para criação de novos registros (usa os mesmos campos da base)
class ProducaoCreate(ProducaoBase):
    pass

# 🔹 Para resposta da API (inclui ID e data formatada)
class ProducaoResponse(ProducaoBase):
    id: int
    criado_em: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.strftime("%d-%m-%Y %H:%M:%S")
        }

