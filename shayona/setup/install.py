import click
from shayona.services.branding_setup_service import setup_branding

def after_install():
    print("Setting up Shayona...")

    setup_branding()
    
    click.secho("Thank you for installing Shayona!", fg="green")
    
def after_app_install(app_name):
    pass