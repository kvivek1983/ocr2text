from app.govt.mappers.gridlines import GridlinesMapper
from app.govt.mappers.cashfree import CashfreeMapper
from app.govt.mappers.hyperverge import HyperVergeMapper

GOVT_MAPPER_REGISTRY = {
    "gridlines": GridlinesMapper(),
    "cashfree": CashfreeMapper(),
    "hyperverge": HyperVergeMapper(),
}
