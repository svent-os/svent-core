export BROWSER=firefox-esr
[ ! -r /etc/profile.d/svent-path.sh ] || . /etc/profile.d/svent-path.sh
autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
_svent_bind_navigation() {
local keymap
for keymap in emacs viins main; do
    bindkey -M "$keymap" '\e[A' up-line-or-beginning-search
    bindkey -M "$keymap" '\eOA' up-line-or-beginning-search
    bindkey -M "$keymap" '\e[B' down-line-or-beginning-search
    bindkey -M "$keymap" '\eOB' down-line-or-beginning-search
    bindkey -M "$keymap" '\e[1;5D' backward-word
    bindkey -M "$keymap" '\e[1;5C' forward-word
    bindkey -M "$keymap" '\e[5D' backward-word
    bindkey -M "$keymap" '\e[5C' forward-word
done
}
_svent_bind_navigation
autoload -Uz add-zsh-hook
add-zsh-hook precmd _svent_bind_navigation
