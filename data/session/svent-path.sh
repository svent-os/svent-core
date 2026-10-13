for svent_path_directory in /usr/local/sbin /usr/sbin /sbin; do
    case ":${PATH:-}:" in
        *":$svent_path_directory:"*) ;;
        *) PATH="${PATH:+$PATH:}$svent_path_directory" ;;
    esac
done
export PATH
unset svent_path_directory
