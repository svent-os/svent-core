autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
for keymap in emacs viins; do
    bindkey -M "$keymap" '\e[A' up-line-or-beginning-search
    bindkey -M "$keymap" '\eOA' up-line-or-beginning-search
    bindkey -M "$keymap" '\e[B' down-line-or-beginning-search
    bindkey -M "$keymap" '\eOB' down-line-or-beginning-search
done
unset keymap
