"""Navigation dans l'appli : onglet Historique, choix du premier jour non joue, jeton (pub si besoin), ouverture de la partie."""
from .game import Player

LIST_TOP, LIST_BOTTOM = 350, 2050      # zone de la liste ou un element est entierement visible


def scroll_to_top(p: Player, swipes: int = 4) -> None:
    """Remonte en haut de la liste (le jour le plus recent est en haut, donc le premier non joue aussi)."""
    for _ in range(swipes):
        p.dev.swipe(540, 700, 540, 1900, 250)
        p.sleep(0.4)


def claim_token(p: Player, attempts: int = 10) -> bool:
    """Apres la pub, le jeton est credite avec un delai cote serveur (« Ton jeton arrive… ») : on touche « Vérifier » jusqu'a ce que la fenetre propose « Jouer ce mot »."""
    for _ in range(attempts):
        screen = p.dev.screen()
        if screen.has("Jouer ce mot"):
            return True
        if screen.has("Vérifier"):
            p.tap_text("Vérifier", wait=3)
        else:
            p.sleep(2)
    return p.dev.screen().has("Jouer ce mot")


def go_to_history(p: Player, attempts: int = 4) -> bool:
    """Atteint l'onglet Historique meme si une fenetre (victoire, jeton, reste d'un run interrompu) cache la barre d'onglets."""
    p.ensure_app()
    for _ in range(attempts):
        if p.tap_text("Historique", last=True, wait=1.5):      # la derniere occurrence est l'onglet du bas
            return True
        if not p.leave_game():
            p.dev.key("KEYCODE_BACK")
            p.sleep(1)
    return False


def open_next_archive(p: Player, scrolls: int = 25) -> bool:
    """Ouvre la partie du premier jour d'archive non joue. Vrai si le champ de saisie est pret. Le motif d'echec est journalise."""
    if not go_to_history(p):
        p.log("!! navigation : onglet Historique introuvable")
        return False
    scroll_to_top(p)
    for _ in range(scrolls):
        node = p.dev.screen().find("Mot à trouver")
        if node is not None and LIST_TOP < node.center[1] < LIST_BOTTOM:
            p.dev.tap(*node.center)
            p.sleep(1.5)
            break
        p.dev.swipe(540, 1600, 540, 1000, 900)                 # petit pas lent : pas de defilement par inertie
        p.sleep(0.8)
    else:
        p.log("!! navigation : aucun jour « Mot à trouver » dans la liste")
        return False
    if not p.tap_text("Jouer ce mot"):
        p.log("!! navigation : bouton « Jouer ce mot » introuvable")
        return False
    p.sleep(1.5)
    if p.dev.screen().has("Regarder une pub"):                 # plus de jeton : une pub en rend un
        p.log("  plus de jeton -> pub")
        p.tap_text("Regarder une pub")
        p.sleep(4)
        p.close_ads()
        p.sleep(1.5)
        if not claim_token(p):
            p.log("!! navigation : jeton non credite apres la pub")
            return False
    if p.dev.screen().has("Jouer ce mot"):                     # fenetre de confirmation « Ce mot te coute un jeton »
        p.tap_text("Jouer ce mot")
        p.sleep(2)
    if not p.focus_input():
        p.log("!! navigation : champ de saisie introuvable")
        return False
    return True
