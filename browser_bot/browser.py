"""Pilotage de Cemanty Web avec Playwright et garde-fous de navigation."""
import base64
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

from .state import WebState, parse_snapshot


DEFAULT_URL = "https://cemanty.fr/jouer/"


class BrowserBotError(RuntimeError):
    pass


class BrowserSafetyError(BrowserBotError):
    pass


class BrowserAdDetected(BrowserSafetyError):
    pass


class RejectedWord(BrowserBotError):
    pass


class GuestLimitReached(BrowserBotError):
    pass


class ArchiveTokenUnavailable(BrowserBotError):
    pass


@dataclass(frozen=True)
class Submission:
    word: str
    score: float
    attempt: Optional[int]
    won: bool


AD_MARKERS = (
    "test ad",
    "learn more",
    "ad 1 of",
    "youtube.com",
    "play.google.com",
)

SAFE_AD_CLOSE_LABELS = {
    "close",
    "close ad",
    "close advertisement",
    "dismiss ad",
    "fermer",
    "fermer la publicité",
    "fermer l'annonce",
}

FRENCH_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"cemanty.fr", "www.cemanty.fr"}
        and parsed.path.rstrip("/") == "/jouer"
    )


def ad_detected(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in AD_MARKERS)


def guest_limit_reached(text: str) -> bool:
    return "Tes essais en invité" in text and "Crée un compte pour continuer le mot du jour" in text


def is_pending_archive_label(text: str) -> bool:
    folded = " ".join(text.casefold().split())
    return "mot à trouver" in folded and "à jouer" in folded


def is_safe_ad_close_label(text: str) -> bool:
    return " ".join(text.casefold().split()) in SAFE_AD_CLOSE_LABELS


class BrowserSession:
    """Une session Playwright dediee, jamais le profil personnel du navigateur."""

    def __init__(self, page, context=None, playwright=None, timeout_ms: int = 15000):
        self.page = page
        self.context = context
        self.playwright = playwright
        self.timeout_ms = timeout_ms
        self._ready = False
        if self.context is not None:
            self.context.on("page", self._close_unexpected_page)

    def _close_unexpected_page(self, page) -> None:
        if page is self.page:
            return
        try:
            page.close()
        except Exception:
            pass

    @classmethod
    def open(cls, profile_dir: str, browser: str = "msedge", headless: bool = False,
             timeout_ms: int = 15000):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserBotError("Playwright absent : lancez pip install -r requirements.txt") from exc

        os.makedirs(profile_dir, exist_ok=True)
        runtime = sync_playwright().start()
        kwargs = {
            "user_data_dir": profile_dir,
            "headless": headless,
            "args": ["--mute-audio"],
        }
        if browser != "chromium":
            kwargs["channel"] = browser
        try:
            context = runtime.chromium.launch_persistent_context(**kwargs)
        except Exception:
            runtime.stop()
            raise
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        return cls(page, context, runtime, timeout_ms)

    def close(self) -> None:
        try:
            if self.context is not None:
                self.context.close()
        finally:
            if self.playwright is not None:
                self.playwright.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _assert_safe_url(self) -> None:
        if not is_allowed_url(self.page.url):
            raise BrowserSafetyError(f"navigation externe interdite : {self.page.url}")

    def _assert_safe_surface(self) -> None:
        self._assert_safe_url()
        body = self.page.locator("body")
        if body.count() and ad_detected(body.inner_text()):
            raise BrowserAdDetected("publicite detectee : aucune interaction effectuee")
        frames = self.page.locator("iframe")
        for index in range(frames.count()):
            frame = frames.nth(index)
            if frame.is_visible() and frame.bounding_box():
                raise BrowserAdDetected("iframe visible detectee : aucune interaction effectuee")

    def _presentation_text(self) -> str:
        presentation = self.page.locator('[role="presentation"]').first
        if presentation.count() and presentation.is_visible():
            return presentation.inner_text()
        return self.page.locator("body").inner_text()

    def _visible_button(self, name: str):
        locator = self.page.get_by_role("button", name=name, exact=True)
        for i in range(locator.count()):
            candidate = locator.nth(i)
            if candidate.is_visible():
                return candidate
        return None

    def _visible_button_containing(self, text: str):
        locator = self.page.get_by_role("button")
        return self._smallest_visible_control_containing(locator, text)

    def _visible_named_control_containing(self, text: str):
        locator = self.page.locator("button, [role='button'], [aria-label]")
        return self._smallest_visible_control_containing(locator, text)

    @staticmethod
    def _smallest_visible_control_containing(locator, text: str):
        matches = []
        for i in range(locator.count()):
            candidate = locator.nth(i)
            if not candidate.is_visible():
                continue
            labels = {
                " ".join((candidate.get_attribute("aria-label") or "").split()),
                " ".join(candidate.inner_text().split()),
            }
            labels.discard("")
            matching_labels = [label for label in labels if text in label]
            if not matching_labels:
                continue
            box = candidate.bounding_box()
            area = box["width"] * box["height"] if box else float("inf")
            # Flutter expose parfois un grand bouton conteneur qui reprend le texte
            # de tous ses enfants. Le libellé le plus proche, puis la plus petite
            # surface, désignent le contrôle réellement demandé.
            distance = min(len(label) - len(text) for label in matching_labels)
            matches.append((distance, area, i, candidate))
        return min(matches, key=lambda item: item[:3])[3] if matches else None

    def _canvas_click(self, locator) -> None:
        """Clique le canvas Flutter aux coordonnees du controle semantique verifie."""
        box = locator.bounding_box()
        if not box:
            raise BrowserBotError("controle visible sans position exploitable")
        self.page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    def _activate_semantic(self, locator) -> None:
        """Active un contrôle Cemanty nommé sans viser le canvas ni une publicité."""
        if locator is None or not locator.is_visible():
            raise BrowserBotError("controle Cemanty attendu mais absent")
        locator.evaluate("element => element.click()")
        self.page.wait_for_timeout(200)

    def _invoke_accessible_button(self, prefix: str) -> None:
        """Invoque un unique bouton du document Edge via UI Automation, sans souris."""
        escaped = prefix.replace("'", "''")
        script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$prefix = '{escaped}'
$windows = @(Get-Process -Name msedge -ErrorAction SilentlyContinue |
    Where-Object {{ $_.MainWindowTitle -like 'Cemanty*' }})
if ($windows.Count -ne 1) {{ exit 2 }}
$docCondition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Document)
$buttonCondition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button)
$deadline = [DateTime]::UtcNow.AddSeconds(4)
do {{
    try {{
        $root = [System.Windows.Automation.AutomationElement]::FromHandle(
            $windows[0].MainWindowHandle)
        $docs = $root.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants, $docCondition)
        if ($docs.Count -eq 1) {{
            $buttons = $docs.Item(0).FindAll(
                [System.Windows.Automation.TreeScope]::Descendants, $buttonCondition)
            $matches = @()
            foreach ($button in $buttons) {{
                try {{
                    if ($button.Current.Name.StartsWith(
                        $prefix, [StringComparison]::OrdinalIgnoreCase)) {{
                        $matches += $button
                    }}
                }} catch {{}}
            }}
            if ($matches.Count -eq 1) {{
                $pattern = $null
                if (-not $matches[0].TryGetCurrentPattern(
                    [System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {{ exit 4 }}
                ([System.Windows.Automation.InvokePattern]$pattern).Invoke()
                exit 0
            }}
        }}
    }} catch {{}}
    Start-Sleep -Milliseconds 100
}} while ([DateTime]::UtcNow -lt $deadline)
exit 5
"""
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Sta", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=8,
            creationflags=creation_flags,
            check=False,
        )
        if completed.returncode == 2:
            raise BrowserSafetyError("fenêtre Edge Cemanty non unique; aucune action effectuée")
        if completed.returncode:
            raise ArchiveTokenUnavailable(
                f"bouton accessible {prefix!r} temporairement indisponible "
                f"(code {completed.returncode})"
            )
        self.page.wait_for_timeout(120)

    def _native_activate(self, locator) -> None:
        """Active le contrôle nommé dans la page sans toucher au pointeur Windows."""
        if locator is None or not locator.is_visible():
            raise BrowserBotError("controle attendu mais absent")
        labels = (
            locator.get_attribute("aria-label") or "",
            locator.inner_text(),
        )
        if any("Regarder une pub" in label for label in labels):
            self._invoke_accessible_button("Regarder une pub")
            return
        # Playwright envoie l'événement au moteur du navigateur. Le pointeur du
        # poste ne bouge pas et aucune autre application ne peut recevoir le clic.
        locator.click(force=True)
        self.page.wait_for_timeout(120)

    def _field(self):
        fields = self.page.locator('[role="textbox"][contenteditable="true"]')
        for i in range(fields.count()):
            candidate = fields.nth(i)
            if candidate.is_visible():
                return candidate
        return None

    def _dismiss_guest_prompt(self) -> bool:
        """Ferme uniquement la sollicitation de creation de compte interne au jeu."""
        attempted = False
        for _ in range(10):
            self._assert_safe_surface()
            text = self._presentation_text()
            if "Tu joues en invité" not in text or "Plus tard" not in text:
                return attempted
            later = self._visible_button("Plus tard")
            if later is None:
                raise BrowserBotError("bouton Plus tard introuvable sur la fenetre invite")
            self._canvas_click(later)
            self.page.wait_for_timeout(500)
            attempted = True
        raise BrowserBotError("fenetre invite impossible a fermer")

    def prepare_game(self, url: str = DEFAULT_URL) -> WebState:
        """Ouvre le jeu, passe le tutoriel et choisit explicitement le mode invite."""
        if not is_allowed_url(url):
            raise BrowserSafetyError(f"URL de depart interdite : {url}")
        if self.page.url != url:
            self.page.goto(url, wait_until="domcontentloaded")
        self._assert_safe_surface()

        deadline = time.monotonic() + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            self._assert_safe_surface()
            field = self._field()
            text = self._presentation_text()
            if guest_limit_reached(text):
                raise GuestLimitReached("limite du mode invite atteinte ; un compte est requis pour continuer")
            state = parse_snapshot(text)
            if field is not None and state.day:
                if not self._ready:
                    # Compose expose sa semantique avant la fin de son ecran de chargement.
                    self.page.wait_for_timeout(6000)
                    self._assert_safe_surface()
                    field = self._field()
                    state = parse_snapshot(self._presentation_text())
                    if field is None or not state.day:
                        continue
                    self._ready = True
                if self._dismiss_guest_prompt():
                    continue
                return state

            action = None
            for label in ("Passer", "Continuer en invité", "Jouer"):
                action = self._visible_button(label)
                if action is not None:
                    break
            if action is not None:
                # Le tutoriel est actionnable avant que le canvas soit totalement peint.
                action.click()
            else:
                self.page.wait_for_timeout(100)
        raise BrowserBotError("plateau de jeu introuvable (tutoriel, connexion ou interface inattendue)")

    def current_state(self) -> WebState:
        self._assert_safe_surface()
        return parse_snapshot(self._presentation_text())

    def wait_for_game(self, url: str = DEFAULT_URL, poll_seconds: float = 30.0) -> WebState:
        """Attend sans cliquer qu'un nouveau plateau jouable apparaisse."""
        if not is_allowed_url(url):
            raise BrowserSafetyError(f"URL de veille interdite : {url}")
        if self.page.url != url:
            self.page.goto(url, wait_until="domcontentloaded")
        else:
            self.page.reload(wait_until="domcontentloaded")
        while True:
            render_deadline = time.monotonic() + self.timeout_ms / 1000
            while time.monotonic() < render_deadline:
                self._assert_safe_surface()
                text = self._presentation_text()
                state = parse_snapshot(text)
                if self._field() is not None and state.day:
                    return state
                if "PROCHAIN MOT DANS" in text:
                    break
                self.page.wait_for_timeout(200)
            else:
                raise BrowserBotError("aucun plateau ni compte a rebours reconnu pendant la veille")
            self.page.wait_for_timeout(max(1.0, min(poll_seconds, 60.0)) * 1000)
            self._assert_safe_surface()
            self.page.reload(wait_until="domcontentloaded")

    def finish_result(self) -> bool:
        """Ferme uniquement le resultat du jeu, par son bouton nomme."""
        self._assert_safe_surface()
        button = self._visible_button("Terminer") or self._visible_button("Fermer")
        if button is None:
            return False
        self._activate_semantic(button)
        self.page.wait_for_timeout(500)
        self._assert_safe_surface()
        return True

    def open_bonus(self) -> bool:
        """Ouvre la partie bonus gratuite, sans archive, duel, jeton ni publicite."""
        self.finish_result()
        self._assert_safe_surface()
        button = self._visible_button_containing("Mot bonus")
        if button is None:
            return False
        label = button.inner_text()
        if "Trouvé en" in label or "revoir la partie" in label.casefold():
            return False
        if "Une partie de plus" not in label:
            raise BrowserSafetyError("bouton bonus inattendu ; ouverture refusee")
        self._activate_semantic(button)
        self.page.wait_for_timeout(400)
        self._assert_safe_surface()
        start = self._visible_button("C'est parti")
        if start is None:
            raise BrowserBotError("confirmation de la partie bonus introuvable")
        self._activate_semantic(start)
        self.page.wait_for_timeout(600)
        self._assert_safe_surface()
        state = parse_snapshot(self._presentation_text())
        if state.day != "bonus" or self._field() is None:
            raise BrowserBotError("plateau de la partie bonus introuvable")
        return True

    def _history_month(self) -> str | None:
        text = self._presentation_text()
        matches = re.findall(rf"(?:{'|'.join(FRENCH_MONTHS)})\s+\d{{4}}", text, re.IGNORECASE)
        # Le premier mois peut appartenir au texte « depuis le 29 juillet 2026 ».
        # Le sélecteur de mois courant est le dernier mois exposé avant la liste.
        return matches[-1] if matches else None

    def _archive_token_count(self) -> int | None:
        tokens = self.page.locator('[aria-label*="jeton d\'archive"]')
        for index in range(tokens.count()):
            label = tokens.nth(index).get_attribute("aria-label") or ""
            match = re.search(r"(\d+)\s+jeton", label)
            if match:
                return int(match.group(1))
        return None

    def open_history(self) -> None:
        """Ouvre l'historique depuis la carte nommee de l'accueil."""
        if self.page.url != "about:blank" and not is_allowed_url(self.page.url):
            raise BrowserSafetyError(f"navigation externe interdite : {self.page.url}")
        self.page.goto(DEFAULT_URL, wait_until="domcontentloaded")
        render_deadline = time.monotonic() + 10.0
        while time.monotonic() < render_deadline:
            if self._visible_button("Jouer") is not None:
                break
            self.page.wait_for_timeout(200)
        self._assert_safe_surface()
        text = self._presentation_text()
        if "Rallume un jour manqué" in text and self._history_month():
            return
        card = self._visible_button_containing("Rattraper un jour manqué")
        if card is None:
            later = self._visible_button("Plus tard")
            if later is not None:
                self._activate_semantic(later)
                self.page.wait_for_timeout(300)
            home = self._visible_button("Jouer")
            if home is not None:
                self._activate_semantic(home)
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    card = self._visible_button_containing("Rattraper un jour manqué")
                    if card is not None:
                        break
                    self.page.wait_for_timeout(100)
        if card is None:
            raise BrowserBotError("carte Rattraper un jour manqué introuvable")
        self._activate_semantic(card)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            self._assert_safe_surface()
            if "Rallume un jour manqué" in self._presentation_text() and self._history_month():
                return
            self.page.wait_for_timeout(100)
        raise BrowserBotError("historique introuvable après son ouverture")

    def _visible_pending_archive(self):
        buttons = self.page.get_by_role("button")
        viewport_height = self.page.evaluate("window.innerHeight")
        for index in range(buttons.count()):
            candidate = buttons.nth(index)
            if not candidate.is_visible() or not is_pending_archive_label(candidate.inner_text()):
                continue
            box = candidate.bounding_box()
            if box and box["y"] < viewport_height and box["y"] + box["height"] > 100:
                return candidate
        return None

    def _previous_month_button(self):
        buttons = self.page.get_by_role("button")
        viewport_width = self.page.evaluate("window.innerWidth")
        candidates = []
        for index in range(buttons.count()):
            candidate = buttons.nth(index)
            if not candidate.is_visible() or candidate.inner_text().strip():
                continue
            box = candidate.bounding_box()
            if box and box["x"] > viewport_width * 0.65 and box["y"] < 80 and box["width"] < 80:
                candidates.append((box["x"], candidate))
        return min(candidates, key=lambda item: item[0])[1] if candidates else None

    def find_pending_archive(self, max_months: int = 18):
        """Trouve le jour jouable le plus recent, sans ouvrir de pub."""
        self.open_history()
        for _ in range(max_months):
            unchanged = 0
            for _scroll in range(20):
                self._assert_safe_surface()
                pending = self._visible_pending_archive()
                if pending is not None:
                    return pending
                before = self._presentation_text()
                self.page.mouse.move(900, max(200, self.page.evaluate("window.innerHeight") - 70))
                self.page.mouse.wheel(0, 560)
                self.page.wait_for_timeout(250)
                after = self._presentation_text()
                unchanged = unchanged + 1 if after == before else 0
                if unchanged >= 2:
                    break
            previous = self._previous_month_button()
            if previous is None:
                return None
            old_month = self._history_month()
            self._activate_semantic(previous)
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline and self._history_month() == old_month:
                self.page.wait_for_timeout(100)
            if self._history_month() == old_month:
                raise BrowserBotError("le mois précédent ne s'ouvre pas")
        return None

    def _visible_ad_iframe(self) -> bool:
        frames = self.page.locator("iframe")
        for index in range(frames.count()):
            frame = frames.nth(index)
            if frame.is_visible() and frame.bounding_box():
                return True
        return False

    def _rewarded_ad_visible(self) -> bool:
        body = self.page.locator("body")
        return self._visible_ad_iframe() or bool(
            body.count() and ad_detected(body.inner_text())
        )

    def _try_close_rewarded_ad(self) -> bool:
        selectors = "button, [role='button'], [aria-label], [title]"
        for frame in self.page.frames:
            controls = frame.locator(selectors)
            for index in range(min(controls.count(), 200)):
                control = controls.nth(index)
                try:
                    if not control.is_visible():
                        continue
                    labels = (
                        control.get_attribute("aria-label") or "",
                        control.get_attribute("title") or "",
                        control.inner_text(),
                    )
                    if any(is_safe_ad_close_label(label) for label in labels if label.strip()):
                        self._native_activate(control)
                        return True
                except Exception:
                    continue
        return False

    def _watch_rewarded_ad(self, log: Callable[[str], None]) -> bool:
        initial_tokens = self._archive_token_count() or 0
        button = None
        button_deadline = time.monotonic() + 5.0
        while time.monotonic() < button_deadline:
            button = self._visible_named_control_containing("Regarder une pub")
            if button is not None:
                break
            self.page.wait_for_timeout(100)
        if button is None:
            log(".. bouton nommé « Regarder une pub » absent du dialogue")
            return False
        self._native_activate(button)

        start_deadline = time.monotonic() + 10.0
        while time.monotonic() < start_deadline:
            if not is_allowed_url(self.page.url):
                raise BrowserSafetyError(f"navigation externe interdite pendant la pub : {self.page.url}")
            if (self._archive_token_count() or 0) > initial_tokens or self._field() is not None:
                return True
            if "Aucune pub disponible" in self._presentation_text():
                log(".. Cemanty indique qu'aucune publicité n'est disponible")
                return False
            if self._rewarded_ad_visible():
                log(".. publicité récompensée en cours — aucun clic dans son contenu")
                break
            self.page.wait_for_timeout(250)
        else:
            log(".. publicité demandée mais indisponible pour le moment")
            return False

        deadline = time.monotonic() + 120.0
        clicked_close = False
        while time.monotonic() < deadline:
            if not is_allowed_url(self.page.url):
                raise BrowserSafetyError(f"navigation externe interdite pendant la pub : {self.page.url}")
            if (self._archive_token_count() or 0) > initial_tokens or self._field() is not None:
                return True
            if self._try_close_rewarded_ad():
                clicked_close = True
                log(".. fermeture sûre de la publicité par son contrôle nommé")
            if clicked_close and not self._rewarded_ad_visible():
                self.page.wait_for_timeout(800)
                if (self._archive_token_count() or 0) > initial_tokens:
                    return True
            self.page.wait_for_timeout(500)
        return False

    def start_next_archive(self, log: Callable[[str], None] = print) -> WebState | None:
        """Ouvre le prochain jour manqué, gagne un jeton si nécessaire, puis retourne son plateau."""
        if is_allowed_url(self.page.url) and self._field() is not None:
            state = self.current_state()
            if state.day and state.day != "bonus":
                log(f".. reprise de l'archive déjà ouverte, mot n° {state.day}")
                return state
        pending = self.find_pending_archive()
        if pending is None:
            return None
        label = " ".join(pending.inner_text().split())
        log(f".. archive sélectionnée : {label}")
        self._activate_semantic(pending)

        deadline = time.monotonic() + 5.0
        play = None
        while time.monotonic() < deadline:
            play = self._visible_button_containing("Jouer ce mot")
            if play is not None:
                break
            self.page.wait_for_timeout(100)
        if play is None:
            raise BrowserBotError("bouton Jouer ce mot introuvable")
        self._activate_semantic(play)

        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if self._field() is not None:
                return self.current_state()
            if "Plus de jeton en réserve" in self._presentation_text():
                break
            self.page.wait_for_timeout(100)
        if "Plus de jeton en réserve" in self._presentation_text():
            if not self._watch_rewarded_ad(log):
                raise ArchiveTokenUnavailable("publicité récompensée indisponible ou impossible à fermer sûrement")
            if self._field() is not None:
                return self.current_state()
            later = self._visible_button("Plus tard")
            if later is not None:
                self._activate_semantic(later)
                self.page.wait_for_timeout(300)
            play = self._visible_button_containing("Jouer ce mot")
            if play is None:
                raise BrowserBotError("bouton Jouer ce mot absent après le gain du jeton")
            self._activate_semantic(play)

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            self._assert_safe_surface()
            if self._field() is not None:
                state = self.current_state()
                if state.day:
                    return state
            self.page.wait_for_timeout(100)
        raise BrowserBotError("plateau d'archive introuvable")

    def submit(self, word: str) -> Submission:
        self._assert_safe_surface()
        self._dismiss_guest_prompt()
        initial_text = self._presentation_text()
        if guest_limit_reached(initial_text):
            raise GuestLimitReached("limite du mode invite atteinte ; un compte est requis pour continuer")
        before = parse_snapshot(initial_text)
        field = self._field()
        if field is None:
            raise BrowserBotError("champ de saisie absent")
        # La focalisation semantique fait apparaitre le vrai champ de saisie Compose.
        field.focus()
        inputs = self.page.locator("input.compose-backing-field")
        if inputs.count() != 1:
            raise BrowserBotError("champ Compose interne introuvable apres focalisation")
        input_field = inputs.first
        input_field.focus()
        input_field.press("Control+A")
        input_field.press_sequentially(word)
        if input_field.input_value() != word:
            raise BrowserBotError("la saisie Compose ne correspond pas au mot demande")
        # Entrée soumet le mot sans cliquer sur le canvas : une publicité superposée
        # ne peut donc jamais être confondue avec la flèche d'envoi du jeu.
        input_field.press("Enter")
        # L'effacement du champ precede parfois la reponse du serveur. On attend donc
        # l'increment de l'essai, pas un simple changement visuel de la page.
        deadline = time.monotonic() + min(self.timeout_ms / 1000, 3.0)
        rejected_after = time.monotonic() + 2.0
        after = before
        while time.monotonic() < deadline:
            self._assert_safe_surface()
            snapshot = self._presentation_text()
            if guest_limit_reached(snapshot):
                raise GuestLimitReached("limite du mode invite atteinte ; un compte est requis pour continuer")
            after = parse_snapshot(snapshot)
            advanced = after.attempt is not None and (before.attempt is None or after.attempt > before.attempt)
            if advanced or after.won:
                break
            current_inputs = self.page.locator("input.compose-backing-field")
            still_typed = bool(
                current_inputs.count()
                and current_inputs.last.input_value().strip().casefold() == word.strip().casefold()
            )
            if still_typed and time.monotonic() >= rejected_after:
                raise RejectedWord(word)
            self.page.wait_for_timeout(50)
        else:
            # Certains mots sont refuses silencieusement par la version web : le champ
            # est vide mais aucun numero d'essai ni score n'est cree.
            raise RejectedWord(word)
        if after.last_score is None:
            raise BrowserBotError(f"score illisible apres l'envoi de {word!r}")
        return Submission(word, after.last_score, after.attempt, after.won)
