from textual.app import App
from textual.widgets import Input, Button, Label
from textual.screen import ModalScreen
import subprocess



# Option 1: Use sudo -S (stdin password)
# You can pass the password via stdin and collect it in a Textual input widget:
class PasswordScreen(ModalScreen[str]):
    """Modal screen to collect sudo password"""
    
    def compose(self):
        yield Label("Enter your sudo password:")
        yield Input(password=True, id="password")
        yield Button("Submit", id="submit")
    
    def on_button_pressed(self):
        password_input = self.query_one("#password", Input)
        self.dismiss(password_input.value)


class MyApp(App[None]):
    async def install_sudoers(self):
        # Show password dialog
        password = await self.push_screen_wait(PasswordScreen())
        
        if not password:
            return False
        
        # Run sudo with password via stdin
        process = subprocess.Popen(
            ['sudo', '-S', 'bash', '-c', 
             f'tee /etc/sudoers.d/myapp > /dev/null << EOF\n{SUDOERS_CONTENT}\nEOF'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=password + '\n')
        
        if process.returncode == 0:
            await self.show_success("Sudoers file installed!")
            return True
        else:
            await self.show_error(f"Failed: {stderr}")
            return False
        
        
###########################################################3


# Option 2: Hybrid approach (better)
# Detect if there's a cached sudo session, and if so, skip the password:
class MyApp(App[None]):
    def check_sudo_cached(self):
        """Check if sudo credentials are already cached"""
        result = subprocess.run(
            ['sudo', '-n', 'true'],  # -n means non-interactive
            capture_output=True
        )
        return result.returncode == 0
    
    async def install_sudoers(self):
        if self.check_sudo_cached():
            # Sudo is cached, just run it
            result = subprocess.run(
                ['sudo', 'bash', '-c', f'tee /etc/sudoers.d/myapp...'],
                capture_output=True
            )
            return result.returncode == 0
        else:
            # Need password - show nice message and suspend
            await self.show_message(
                "Setup requires sudo access.\n"
                "You'll be prompted for your password in the terminal."
            )
            
            with self.suspend():
                result = subprocess.run(
                    ['sudo', 'bash', '-c', f'tee /etc/sudoers.d/myapp...']
                )
            
            return result.returncode == 0