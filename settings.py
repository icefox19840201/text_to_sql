from starlette.templating import Jinja2Templates
import os
template_dir=os.path.join(os.path.dirname(__file__),"templates")
template=Jinja2Templates(directory=str(template_dir))
mysql_db_uri="mysql+pymysql://icefox1:123456@localhost:3306/text_to_sql"
template_dir=os.path.join(os.path.dirname(__file__),"templates")