from root_urls import app
import dotenv
import uvicorn
#----------------------初始化---------------------------------
dotenv.load_dotenv()


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)


