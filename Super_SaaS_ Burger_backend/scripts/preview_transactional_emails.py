"""Render sample HTML locally. Does not send mail or load credentials."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.transactional_emails import recovery_message,welcome_message,password_changed_message,LOGO_CID,logo_content

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/tmp/fomizero-email-preview')
    args=parser.parse_args();directory=Path(args.output);directory.mkdir(parents=True,exist_ok=True)
    messages={'recuperacao':recovery_message('Ana Silva','Cantina Exemplo','https://cantina.fomizero.com.br/redefinir-senha#token=exemplo-sem-validade'),
        'boas-vindas':welcome_message('Ana Silva','Cantina Exemplo','cantina'),
        'senha-alterada':password_changed_message('Ana Silva','Cantina Exemplo','cantina')}
    for key,message in messages.items():
        # Preview only: browsers do not resolve email MIME Content-ID references.
        (directory/(key+'.html')).write_text(message.html.replace('cid:'+LOGO_CID,'data:image/png;base64,'+logo_content()))
        (directory/(key+'.txt')).write_text(message.text)
    print(f'3 modelos de exemplo gravados em {directory}. Nenhum e-mail foi enviado.')
if __name__=='__main__':main()
