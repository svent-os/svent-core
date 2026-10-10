export ZSH_DISABLE_COMPFIX=true

HISTFILE="$HOME/.zsh_history"
HISTSIZE=10000
SAVEHIST=10000
setopt HIST_IGNORE_DUPS HIST_IGNORE_SPACE SHARE_HISTORY INC_APPEND_HISTORY

setopt AUTO_CD INTERACTIVE_COMMENTS PROMPT_SUBST

autoload -Uz compinit && compinit
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

autoload -Uz colors && colors
autoload -Uz vcs_info
zstyle ':vcs_info:*' enable git
zstyle ':vcs_info:git:*' formats ' %F{yellow}[%b]%f'
zstyle ':vcs_info:git:*' actionformats ' %F{yellow}[%b|%a]%f'
precmd_functions+=(vcs_info)

PS1='%F{red}%B%n@%m%b%f%F{yellow}:%f%F{red}%B%~%b%f${vcs_info_msg_0_}%F{yellow}\$%f '

LS_COLORS="di=38;2;255;200;80:fi=38;2;220;220;220:ex=38;2;255;180;60:ln=38;2;120;200;255:so=38;2;180;140;255:bd=38;2;255;120;120:cd=38;2;255;160;80:ow=38;2;255;200;80:tw=38;2;255;200;80:st=38;2;100;180;255:or=38;2;255;80;80"
export LS_COLORS

alias ls='ls --color=auto'
alias ll='ls -la'
alias la='ls -A'

export PATH="$HOME/.local/bin:$PATH"

[ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ] && \
  source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
if [ -f /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]; then
  source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
  ZSH_HIGHLIGHT_STYLES[command]='fg=71,bold'
  ZSH_HIGHLIGHT_STYLES[builtin]='fg=117,bold'
  ZSH_HIGHLIGHT_STYLES[function]='fg=179,bold'
  ZSH_HIGHLIGHT_STYLES[alias]='fg=176,bold'
  ZSH_HIGHLIGHT_STYLES[external]='fg=111,bold'
  ZSH_HIGHLIGHT_STYLES[precommand]='fg=203,bold'
  ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=109,bold'
  ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=109,bold'
  ZSH_HIGHLIGHT_STYLES[arg]='fg=251,bold'
  ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=210,bold'
fi
