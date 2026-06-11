"""
Управление нашими товарами и товарами конкурентов.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.competitor import Competitor
from app.models.enums import MatchStatus
from app.models.product import CompetitorProduct, MyProduct, ProductCategory

router = APIRouter(prefix="/products")
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def list_products(request: Request, db: Session = Depends(get_db)):
    """Страница управления товарами."""
    my_products = (
        db.query(MyProduct)
        .options(joinedload(MyProduct.category))
        .order_by(MyProduct.name)
        .all()
    )
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()
    competitors = db.query(Competitor).order_by(Competitor.name).all()
    competitor_products = (
        db.query(CompetitorProduct)
        .options(
            joinedload(CompetitorProduct.competitor),
            joinedload(CompetitorProduct.category),
        )
        .order_by(CompetitorProduct.name)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "my_products": my_products,
            "categories": categories,
            "competitors": competitors,
            "competitor_products": competitor_products,
            "match_statuses": MatchStatus,
        },
    )


@router.post("/my/add")
def add_my_product(
    name: str = Form(...),
    category_id: str = Form(""),
    my_price: float = Form(...),
    db: Session = Depends(get_db),
):
    """Добавить наш эталонный товар."""
    product = MyProduct(
        name=name.strip(),
        category_id=int(category_id) if category_id else None,
        my_price=my_price,
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)


@router.post("/category/add")
def add_category(
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Добавить категорию товаров."""
    category = ProductCategory(name=name.strip())
    db.add(category)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)


@router.post("/competitor/add")
def add_competitor_product(
    competitor_id: int = Form(...),
    name: str = Form(...),
    url: str = Form(""),
    category_id: str = Form(""),
    db: Session = Depends(get_db),
):
    """Добавить ссылку конкурента на товар."""
    product = CompetitorProduct(
        competitor_id=competitor_id,
        name=name.strip(),
        url=url.strip() if url else None,
        category_id=int(category_id) if category_id else None,
        match_status=MatchStatus.UNMATCHED,
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)
