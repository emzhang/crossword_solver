!/usr/bin/env zsh

for num in (seq 1 19500)
        wget --no-verbose --content-disposition "https://www.nytimes.com/svc/crosswords/v2/puzzle/$num.puz" \
                --header='Referer: https://www.nytimes.com/crosswords/archive/daily'
                # --header='Cookie: nyt-a=[redacted]; NYT-S=[redacted]; nyt-auth-method=[redacted]; nyt-m=[redacted];'
        sleep 5
end