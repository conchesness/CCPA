
from app import app
import os

if __name__ == "__main__":
    
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

    root = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(root, 'nltk_data')
    os.chdir(download_dir)
    nltk.data.path.append(download_dir)
    
    # app.run(debug="True")
    app.run()