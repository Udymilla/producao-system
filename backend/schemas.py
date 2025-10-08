from datetime import datetime
from pydantic import BaseModel

# 🔹 Classe base — usada para criação e atualização
class ProducaoBase(BaseModel):
    ficha_id: int              # 🔹 nova coluna
    operador: str
    modelo: str
    servico: str
    tamanho: str
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
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class StatusFicha(str, Enum):
    EM_PRODUCAO = "em_producao"
    EM_ESTOQUE = "em_estoque"
    FINALIZADA = "finalizada"

# ✅ Dados recebidos ao criar uma ficha
class FichaCreate(BaseModel):
    modelo: str
    funcao: str
    quantidade_total: int
    setor_atual: str | None = None

# ✅ Dados retornados pela API
class FichaResponse(FichaCreate):
    id: int
    numero_ficha: str
    status: StatusFicha
    criado_em: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.strftime("%d-%m-%Y %H:%M:%S")
        }

