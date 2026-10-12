autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
for keymap in emacs viins; do
    bindkey -M "$keymap" '\e[A' up-line-or-beginning-search
    bindkey -M "$keymap" '\eOA' up-line-or-beginning-search
    bindkey -M "$keymap" '\e[B' down-line-or-beginning-search
    bindkey -M "$keymap" '\eOB' down-line-or-beginning-search
    bindkey -M "$keymap" '\e[1;5D' backward-word
    bindkey -M "$keymap" '\e[1;5C' forward-word
    bindkey -M "$keymap" '\e[5D' backward-word
    bindkey -M "$keymap" '\e[5C' forward-word
done
unset keymap
