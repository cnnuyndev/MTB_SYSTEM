"# MTB_SYSTEM" 

# python -m venv
# venv/scripts/activate
# pip install -r .\requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver