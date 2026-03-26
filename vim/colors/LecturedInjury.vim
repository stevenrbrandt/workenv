
" Vim color file
" Maintainer:   Your name <youremail@something.com>
" Last Change:  
" URL:		

" cool help screens
" :he group-name
" :he highlight-groups
" :he cterm-colors

" your pick:
set background=light
hi clear
if exists("syntax_on")
    syntax reset
endif
let g:colors_name="torture"

"hi Normal

" OR

" highlight clear Normal
" set background&
" highlight clear
" if &background == "light"
"   highlight Error ...
"   ...
" else
"   highlight Error ...
"   ...
" endif

" A good way to see what your colorscheme does is to follow this procedure:
" :w 
" :so % 
"
" Then to see what the current setting is use the highlight command.  
" For example,
" 	:hi Cursor
" gives
"	Cursor         xxx guifg=bg guibg=fg 
 	
" Uncomment and complete the commands you want to change from the default.

"hi Cursor		
"hi CursorIM	
"hi Directory	
"See https://github.com/guns/xterm-color-table.vim

hi Added guifg=#8a8a8a guibg=#000000
hi Added ctermfg=245 ctermbg=16


hi Boolean guifg=#d78787 guibg=#000000
hi Boolean ctermfg=174 ctermbg=16


hi Changed guifg=#878787 guibg=#000000
hi Changed ctermfg=102 ctermbg=16


hi Character guifg=#d7af00 guibg=#000000
hi Character ctermfg=178 ctermbg=16


hi CocBold guifg=#5fff5f guibg=#000000
hi CocBold ctermfg=83 ctermbg=16


hi CocCodeLens guifg=#875fd7 guibg=#000000
hi CocCodeLens ctermfg=98 ctermbg=16


hi CocCursorRange guifg=#af5fd7 guibg=#000000
hi CocCursorRange ctermfg=134 ctermbg=16


hi CocDeprecatedHighlight guifg=#ff5f87 guibg=#000000
hi CocDeprecatedHighlight ctermfg=204 ctermbg=16


hi CocDisabled guifg=#ff0087 guibg=#000000
hi CocDisabled ctermfg=198 ctermbg=16


hi CocErrorFloat guifg=#87af87 guibg=#000000
hi CocErrorFloat ctermfg=108 ctermbg=16


hi CocErrorHighlight guifg=#5f00d7 guibg=#000000
hi CocErrorHighlight ctermfg=56 ctermbg=16


hi CocErrorSign guifg=#00afd7 guibg=#000000
hi CocErrorSign ctermfg=38 ctermbg=16


hi CocErrorVirtualText guifg=#5f875f guibg=#000000
hi CocErrorVirtualText ctermfg=65 ctermbg=16


hi CocFadeOut guifg=#af00d7 guibg=#000000
hi CocFadeOut ctermfg=128 ctermbg=16


hi CocFloatActive guifg=#d7af5f guibg=#000000
hi CocFloatActive ctermfg=179 ctermbg=16


hi CocFloatBorder guifg=#87af5f guibg=#000000
hi CocFloatBorder ctermfg=107 ctermbg=16


hi CocFloatDividingLine guifg=#005fff guibg=#000000
hi CocFloatDividingLine ctermfg=27 ctermbg=16


hi CocFloatSbar guifg=#808080 guibg=#000000
hi CocFloatSbar ctermfg=244 ctermbg=16


hi CocFloatThumb guifg=#6c6c6c guibg=#000000
hi CocFloatThumb ctermfg=242 ctermbg=16


hi CocFloating guifg=#875f87 guibg=#000000
hi CocFloating ctermfg=96 ctermbg=16


hi CocHighlightRead guifg=#6c6c6c guibg=#000000
hi CocHighlightRead ctermfg=242 ctermbg=16


hi CocHighlightText guifg=#00d7d7 guibg=#000000
hi CocHighlightText ctermfg=44 ctermbg=16


hi CocHighlightWrite guifg=#5f00d7 guibg=#000000
hi CocHighlightWrite ctermfg=56 ctermbg=16


hi CocHintFloat guifg=#5faf87 guibg=#000000
hi CocHintFloat ctermfg=72 ctermbg=16


hi CocHintHighlight guifg=#af8787 guibg=#000000
hi CocHintHighlight ctermfg=138 ctermbg=16


hi CocHintSign guifg=#875f5f guibg=#000000
hi CocHintSign ctermfg=95 ctermbg=16


hi CocHintVirtualText guifg=#00afff guibg=#000000
hi CocHintVirtualText ctermfg=39 ctermbg=16


hi CocHoverRange guifg=#0087d7 guibg=#000000
hi CocHoverRange ctermfg=32 ctermbg=16


hi CocInfoFloat guifg=#afaf00 guibg=#000000
hi CocInfoFloat ctermfg=142 ctermbg=16


hi CocInfoHighlight guifg=#767676 guibg=#000000
hi CocInfoHighlight ctermfg=243 ctermbg=16


hi CocInfoSign guifg=#afd75f guibg=#000000
hi CocInfoSign ctermfg=149 ctermbg=16


hi CocInfoVirtualText guifg=#d7d700 guibg=#000000
hi CocInfoVirtualText ctermfg=184 ctermbg=16


hi CocInlayHint guifg=#5faf5f guibg=#000000
hi CocInlayHint ctermfg=71 ctermbg=16


hi CocInlayHintParameter guifg=#af875f guibg=#000000
hi CocInlayHintParameter ctermfg=137 ctermbg=16


hi CocInlayHintType guifg=#9e9e9e guibg=#000000
hi CocInlayHintType ctermfg=247 ctermbg=16


hi CocInlineAnnotation guifg=#875f87 guibg=#000000
hi CocInlineAnnotation ctermfg=96 ctermbg=16


hi CocInlineVirtualText guifg=#8787d7 guibg=#000000
hi CocInlineVirtualText ctermfg=104 ctermbg=16


hi CocInputBoxVirtualText guifg=#5fff87 guibg=#000000
hi CocInputBoxVirtualText ctermfg=84 ctermbg=16


hi CocItalic guifg=#d7af5f guibg=#000000
hi CocItalic ctermfg=179 ctermbg=16


hi CocLink guifg=#8787d7 guibg=#000000
hi CocLink ctermfg=104 ctermbg=16


hi CocLinkedEditing guifg=#8700ff guibg=#000000
hi CocLinkedEditing ctermfg=93 ctermbg=16


hi CocListBgBlack guifg=#ff5f87 guibg=#000000
hi CocListBgBlack ctermfg=204 ctermbg=16


hi CocListBgBlue guifg=#ff00af guibg=#000000
hi CocListBgBlue ctermfg=199 ctermbg=16


hi CocListBgCyan guifg=#ff00d7 guibg=#000000
hi CocListBgCyan ctermfg=200 ctermbg=16


hi CocListBgGreen guifg=#5f87d7 guibg=#000000
hi CocListBgGreen ctermfg=68 ctermbg=16


hi CocListBgGrey guifg=#00ff87 guibg=#000000
hi CocListBgGrey ctermfg=48 ctermbg=16


hi CocListBgMagenta guifg=#5fd700 guibg=#000000
hi CocListBgMagenta ctermfg=76 ctermbg=16


hi CocListBgRed guifg=#af5faf guibg=#000000
hi CocListBgRed ctermfg=133 ctermbg=16


hi CocListBgWhite guifg=#ff5f5f guibg=#000000
hi CocListBgWhite ctermfg=203 ctermbg=16


hi CocListBgYellow guifg=#5fd75f guibg=#000000
hi CocListBgYellow ctermfg=77 ctermbg=16


hi CocListBlackBlack guifg=#ff0087 guibg=#000000
hi CocListBlackBlack ctermfg=198 ctermbg=16


hi CocListBlackBlue guifg=#5f5fd7 guibg=#000000
hi CocListBlackBlue ctermfg=62 ctermbg=16


hi CocListBlackCyan guifg=#87ff00 guibg=#000000
hi CocListBlackCyan ctermfg=118 ctermbg=16


hi CocListBlackGreen guifg=#5f5faf guibg=#000000
hi CocListBlackGreen ctermfg=61 ctermbg=16


hi CocListBlackGrey guifg=#afd700 guibg=#000000
hi CocListBlackGrey ctermfg=148 ctermbg=16


hi CocListBlackMagenta guifg=#00afd7 guibg=#000000
hi CocListBlackMagenta ctermfg=38 ctermbg=16


hi CocListBlackRed guifg=#00d7af guibg=#000000
hi CocListBlackRed ctermfg=43 ctermbg=16


hi CocListBlackWhite guifg=#87ff5f guibg=#000000
hi CocListBlackWhite ctermfg=119 ctermbg=16


hi CocListBlackYellow guifg=#00d787 guibg=#000000
hi CocListBlackYellow ctermfg=42 ctermbg=16


hi CocListBlueBlack guifg=#875fd7 guibg=#000000
hi CocListBlueBlack ctermfg=98 ctermbg=16


hi CocListBlueBlue guifg=#af5faf guibg=#000000
hi CocListBlueBlue ctermfg=133 ctermbg=16


hi CocListBlueCyan guifg=#ff0087 guibg=#000000
hi CocListBlueCyan ctermfg=198 ctermbg=16


hi CocListBlueGreen guifg=#d7af00 guibg=#000000
hi CocListBlueGreen ctermfg=178 ctermbg=16


hi CocListBlueGrey guifg=#87875f guibg=#000000
hi CocListBlueGrey ctermfg=101 ctermbg=16


hi CocListBlueMagenta guifg=#5f87ff guibg=#000000
hi CocListBlueMagenta ctermfg=69 ctermbg=16


hi CocListBlueRed guifg=#875f87 guibg=#000000
hi CocListBlueRed ctermfg=96 ctermbg=16


hi CocListBlueWhite guifg=#ff875f guibg=#000000
hi CocListBlueWhite ctermfg=209 ctermbg=16


hi CocListBlueYellow guifg=#0087d7 guibg=#000000
hi CocListBlueYellow ctermfg=32 ctermbg=16


hi CocListCyanBlack guifg=#00ffaf guibg=#000000
hi CocListCyanBlack ctermfg=49 ctermbg=16


hi CocListCyanBlue guifg=#00ffd7 guibg=#000000
hi CocListCyanBlue ctermfg=50 ctermbg=16


hi CocListCyanCyan guifg=#5f00d7 guibg=#000000
hi CocListCyanCyan ctermfg=56 ctermbg=16


hi CocListCyanGreen guifg=#af8787 guibg=#000000
hi CocListCyanGreen ctermfg=138 ctermbg=16


hi CocListCyanGrey guifg=#5f5fff guibg=#000000
hi CocListCyanGrey ctermfg=63 ctermbg=16


hi CocListCyanMagenta guifg=#5f87d7 guibg=#000000
hi CocListCyanMagenta ctermfg=68 ctermbg=16


hi CocListCyanRed guifg=#87ff5f guibg=#000000
hi CocListCyanRed ctermfg=119 ctermbg=16


hi CocListCyanWhite guifg=#5fd787 guibg=#000000
hi CocListCyanWhite ctermfg=78 ctermbg=16


hi CocListCyanYellow guifg=#00d7ff guibg=#000000
hi CocListCyanYellow ctermfg=45 ctermbg=16


hi CocListFgBlack guifg=#949494 guibg=#000000
hi CocListFgBlack ctermfg=246 ctermbg=16


hi CocListFgBlue guifg=#5f00ff guibg=#000000
hi CocListFgBlue ctermfg=57 ctermbg=16


hi CocListFgCyan guifg=#af5fd7 guibg=#000000
hi CocListFgCyan ctermfg=134 ctermbg=16


hi CocListFgGreen guifg=#5f5f87 guibg=#000000
hi CocListFgGreen ctermfg=60 ctermbg=16


hi CocListFgGrey guifg=#af8700 guibg=#000000
hi CocListFgGrey ctermfg=136 ctermbg=16


hi CocListFgMagenta guifg=#808080 guibg=#000000
hi CocListFgMagenta ctermfg=244 ctermbg=16


hi CocListFgRed guifg=#5fff00 guibg=#000000
hi CocListFgRed ctermfg=82 ctermbg=16


hi CocListFgWhite guifg=#87ff00 guibg=#000000
hi CocListFgWhite ctermfg=118 ctermbg=16


hi CocListFgYellow guifg=#00ffaf guibg=#000000
hi CocListFgYellow ctermfg=49 ctermbg=16


hi CocListGreenBlack guifg=#af5f5f guibg=#000000
hi CocListGreenBlack ctermfg=131 ctermbg=16


hi CocListGreenBlue guifg=#afd700 guibg=#000000
hi CocListGreenBlue ctermfg=148 ctermbg=16


hi CocListGreenCyan guifg=#ffaf00 guibg=#000000
hi CocListGreenCyan ctermfg=214 ctermbg=16


hi CocListGreenGreen guifg=#5f5f87 guibg=#000000
hi CocListGreenGreen ctermfg=60 ctermbg=16


hi CocListGreenGrey guifg=#5faf5f guibg=#000000
hi CocListGreenGrey ctermfg=71 ctermbg=16


hi CocListGreenMagenta guifg=#d78700 guibg=#000000
hi CocListGreenMagenta ctermfg=172 ctermbg=16


hi CocListGreenRed guifg=#d70087 guibg=#000000
hi CocListGreenRed ctermfg=162 ctermbg=16


hi CocListGreenWhite guifg=#0087d7 guibg=#000000
hi CocListGreenWhite ctermfg=32 ctermbg=16


hi CocListGreenYellow guifg=#6c6c6c guibg=#000000
hi CocListGreenYellow ctermfg=242 ctermbg=16


hi CocListGreyBlack guifg=#5fff00 guibg=#000000
hi CocListGreyBlack ctermfg=82 ctermbg=16


hi CocListGreyBlue guifg=#949494 guibg=#000000
hi CocListGreyBlue ctermfg=246 ctermbg=16


hi CocListGreyCyan guifg=#af5faf guibg=#000000
hi CocListGreyCyan ctermfg=133 ctermbg=16


hi CocListGreyGreen guifg=#5f87ff guibg=#000000
hi CocListGreyGreen ctermfg=69 ctermbg=16


hi CocListGreyGrey guifg=#87af00 guibg=#000000
hi CocListGreyGrey ctermfg=106 ctermbg=16


hi CocListGreyMagenta guifg=#d700af guibg=#000000
hi CocListGreyMagenta ctermfg=163 ctermbg=16


hi CocListGreyRed guifg=#5f87ff guibg=#000000
hi CocListGreyRed ctermfg=69 ctermbg=16


hi CocListGreyWhite guifg=#8700af guibg=#000000
hi CocListGreyWhite ctermfg=91 ctermbg=16


hi CocListGreyYellow guifg=#d70087 guibg=#000000
hi CocListGreyYellow ctermfg=162 ctermbg=16


hi CocListLine guifg=#5fff87 guibg=#000000
hi CocListLine ctermfg=84 ctermbg=16


hi CocListMagentaBlack guifg=#d7af5f guibg=#000000
hi CocListMagentaBlack ctermfg=179 ctermbg=16


hi CocListMagentaBlue guifg=#875f5f guibg=#000000
hi CocListMagentaBlue ctermfg=95 ctermbg=16


hi CocListMagentaCyan guifg=#d7af00 guibg=#000000
hi CocListMagentaCyan ctermfg=178 ctermbg=16


hi CocListMagentaGreen guifg=#5fd787 guibg=#000000
hi CocListMagentaGreen ctermfg=78 ctermbg=16


hi CocListMagentaGrey guifg=#5f5f87 guibg=#000000
hi CocListMagentaGrey ctermfg=60 ctermbg=16


hi CocListMagentaMagenta guifg=#5f00ff guibg=#000000
hi CocListMagentaMagenta ctermfg=57 ctermbg=16


hi CocListMagentaRed guifg=#d7005f guibg=#000000
hi CocListMagentaRed ctermfg=161 ctermbg=16


hi CocListMagentaWhite guifg=#af5f87 guibg=#000000
hi CocListMagentaWhite ctermfg=132 ctermbg=16


hi CocListMagentaYellow guifg=#875f5f guibg=#000000
hi CocListMagentaYellow ctermfg=95 ctermbg=16


hi CocListMode guifg=#87af87 guibg=#000000
hi CocListMode ctermfg=108 ctermbg=16


hi CocListPath guifg=#afaf00 guibg=#000000
hi CocListPath ctermfg=142 ctermbg=16


hi CocListRedBlack guifg=#5fd7af guibg=#000000
hi CocListRedBlack ctermfg=79 ctermbg=16


hi CocListRedBlue guifg=#87af5f guibg=#000000
hi CocListRedBlue ctermfg=107 ctermbg=16


hi CocListRedCyan guifg=#af875f guibg=#000000
hi CocListRedCyan ctermfg=137 ctermbg=16


hi CocListRedGreen guifg=#af00d7 guibg=#000000
hi CocListRedGreen ctermfg=128 ctermbg=16


hi CocListRedGrey guifg=#ff5f00 guibg=#000000
hi CocListRedGrey ctermfg=202 ctermbg=16


hi CocListRedMagenta guifg=#afff00 guibg=#000000
hi CocListRedMagenta ctermfg=154 ctermbg=16


hi CocListRedRed guifg=#87afaf guibg=#000000
hi CocListRedRed ctermfg=109 ctermbg=16


hi CocListRedWhite guifg=#af875f guibg=#000000
hi CocListRedWhite ctermfg=137 ctermbg=16


hi CocListRedYellow guifg=#87d700 guibg=#000000
hi CocListRedYellow ctermfg=112 ctermbg=16


hi CocListSearch guifg=#000000 guibg=#5faf5f
hi CocListSearch ctermfg=16 ctermbg=71


hi CocListWhiteBlack guifg=#ff5f5f guibg=#000000
hi CocListWhiteBlack ctermfg=203 ctermbg=16


hi CocListWhiteBlue guifg=#00afd7 guibg=#000000
hi CocListWhiteBlue ctermfg=38 ctermbg=16


hi CocListWhiteCyan guifg=#87d75f guibg=#000000
hi CocListWhiteCyan ctermfg=113 ctermbg=16


hi CocListWhiteGreen guifg=#5f5fd7 guibg=#000000
hi CocListWhiteGreen ctermfg=62 ctermbg=16


hi CocListWhiteGrey guifg=#afd700 guibg=#000000
hi CocListWhiteGrey ctermfg=148 ctermbg=16


hi CocListWhiteMagenta guifg=#5f5fd7 guibg=#000000
hi CocListWhiteMagenta ctermfg=62 ctermbg=16


hi CocListWhiteRed guifg=#af00d7 guibg=#000000
hi CocListWhiteRed ctermfg=128 ctermbg=16


hi CocListWhiteWhite guifg=#5fd7af guibg=#000000
hi CocListWhiteWhite ctermfg=79 ctermbg=16


hi CocListWhiteYellow guifg=#af5f5f guibg=#000000
hi CocListWhiteYellow ctermfg=131 ctermbg=16


hi CocListYellowBlack guifg=#5fff5f guibg=#000000
hi CocListYellowBlack ctermfg=83 ctermbg=16


hi CocListYellowBlue guifg=#00d7af guibg=#000000
hi CocListYellowBlue ctermfg=43 ctermbg=16


hi CocListYellowCyan guifg=#875f5f guibg=#000000
hi CocListYellowCyan ctermfg=95 ctermbg=16


hi CocListYellowGreen guifg=#5fff00 guibg=#000000
hi CocListYellowGreen ctermfg=82 ctermbg=16


hi CocListYellowGrey guifg=#af87af guibg=#000000
hi CocListYellowGrey ctermfg=139 ctermbg=16


hi CocListYellowMagenta guifg=#d700d7 guibg=#000000
hi CocListYellowMagenta ctermfg=164 ctermbg=16


hi CocListYellowRed guifg=#af00af guibg=#000000
hi CocListYellowRed ctermfg=127 ctermbg=16


hi CocListYellowWhite guifg=#875f5f guibg=#000000
hi CocListYellowWhite ctermfg=95 ctermbg=16


hi CocListYellowYellow guifg=#af5f87 guibg=#000000
hi CocListYellowYellow ctermfg=132 ctermbg=16


hi CocMarkdownLink guifg=#d7005f guibg=#000000
hi CocMarkdownLink ctermfg=161 ctermbg=16


hi CocMenuSel guifg=#ffd700 guibg=#000000
hi CocMenuSel ctermfg=220 ctermbg=16


hi CocNotificationButton guifg=#d7af00 guibg=#000000
hi CocNotificationButton ctermfg=178 ctermbg=16


hi CocNotificationError guifg=#5fd787 guibg=#000000
hi CocNotificationError ctermfg=78 ctermbg=16


hi CocNotificationInfo guifg=#afd75f guibg=#000000
hi CocNotificationInfo ctermfg=149 ctermbg=16


hi CocNotificationKey guifg=#ff8700 guibg=#000000
hi CocNotificationKey ctermfg=208 ctermbg=16


hi CocNotificationProgress guifg=#5fafd7 guibg=#000000
hi CocNotificationProgress ctermfg=74 ctermbg=16


hi CocNotificationWarning guifg=#af0087 guibg=#000000
hi CocNotificationWarning ctermfg=126 ctermbg=16


hi CocPumDeprecated guifg=#5fff00 guibg=#000000
hi CocPumDeprecated ctermfg=82 ctermbg=16


hi CocPumDetail guifg=#875faf guibg=#000000
hi CocPumDetail ctermfg=97 ctermbg=16


hi CocPumMenu guifg=#0087d7 guibg=#000000
hi CocPumMenu ctermfg=32 ctermbg=16


hi CocPumSearch guifg=#000000 guibg=#5fafd7
hi CocPumSearch ctermfg=16 ctermbg=74


hi CocPumShortcut guifg=#af5fd7 guibg=#000000
hi CocPumShortcut ctermfg=134 ctermbg=16


hi CocPumVirtualText guifg=#005fd7 guibg=#000000
hi CocPumVirtualText ctermfg=26 ctermbg=16


hi CocSearch guifg=#000000 guibg=#5f5fd7
hi CocSearch ctermfg=16 ctermbg=62


hi CocSelectedRange guifg=#d7ff00 guibg=#000000
hi CocSelectedRange ctermfg=190 ctermbg=16


hi CocSelectedText guifg=#00ff87 guibg=#000000
hi CocSelectedText ctermfg=48 ctermbg=16


hi CocSemModDeprecated guifg=#af87af guibg=#000000
hi CocSemModDeprecated ctermfg=139 ctermbg=16


hi CocSemTypeBoolean guifg=#00ffaf guibg=#000000
hi CocSemTypeBoolean ctermfg=49 ctermbg=16


hi CocSemTypeClass guifg=#5f5f87 guibg=#000000
hi CocSemTypeClass ctermfg=60 ctermbg=16


hi CocSemTypeComment guifg=#ff0087 guibg=#000000
hi CocSemTypeComment ctermfg=198 ctermbg=16


hi CocSemTypeDecorator guifg=#00afff guibg=#000000
hi CocSemTypeDecorator ctermfg=39 ctermbg=16


hi CocSemTypeEnum guifg=#9e9e9e guibg=#000000
hi CocSemTypeEnum ctermfg=247 ctermbg=16


hi CocSemTypeEnumMember guifg=#949494 guibg=#000000
hi CocSemTypeEnumMember ctermfg=246 ctermbg=16


hi CocSemTypeEvent guifg=#5f875f guibg=#000000
hi CocSemTypeEvent ctermfg=65 ctermbg=16


hi CocSemTypeFunction guifg=#ff5f87 guibg=#000000
hi CocSemTypeFunction ctermfg=204 ctermbg=16


hi CocSemTypeInterface guifg=#875fd7 guibg=#000000
hi CocSemTypeInterface ctermfg=98 ctermbg=16


hi CocSemTypeKeyword guifg=#5fff00 guibg=#000000
hi CocSemTypeKeyword ctermfg=82 ctermbg=16


hi CocSemTypeMacro guifg=#af0087 guibg=#000000
hi CocSemTypeMacro ctermfg=126 ctermbg=16


hi CocSemTypeMethod guifg=#d78787 guibg=#000000
hi CocSemTypeMethod ctermfg=174 ctermbg=16


hi CocSemTypeModifier guifg=#5f5fd7 guibg=#000000
hi CocSemTypeModifier ctermfg=62 ctermbg=16


hi CocSemTypeNamespace guifg=#d75f00 guibg=#000000
hi CocSemTypeNamespace ctermfg=166 ctermbg=16


hi CocSemTypeNumber guifg=#af875f guibg=#000000
hi CocSemTypeNumber ctermfg=137 ctermbg=16


hi CocSemTypeOperator guifg=#af875f guibg=#000000
hi CocSemTypeOperator ctermfg=137 ctermbg=16


hi CocSemTypeParameter guifg=#ff8700 guibg=#000000
hi CocSemTypeParameter ctermfg=208 ctermbg=16


hi CocSemTypeProperty guifg=#d75faf guibg=#000000
hi CocSemTypeProperty ctermfg=169 ctermbg=16


hi CocSemTypeRegexp guifg=#5faf5f guibg=#000000
hi CocSemTypeRegexp ctermfg=71 ctermbg=16


hi CocSemTypeString guifg=#00afd7 guibg=#000000
hi CocSemTypeString ctermfg=38 ctermbg=16


hi CocSemTypeStruct guifg=#875f87 guibg=#000000
hi CocSemTypeStruct ctermfg=96 ctermbg=16


hi CocSemTypeType guifg=#5f87ff guibg=#000000
hi CocSemTypeType ctermfg=69 ctermbg=16


hi CocSemTypeTypeParameter guifg=#00d7af guibg=#000000
hi CocSemTypeTypeParameter ctermfg=43 ctermbg=16


hi CocSemTypeVariable guifg=#005fff guibg=#000000
hi CocSemTypeVariable ctermfg=27 ctermbg=16


hi CocSnippetVisual guifg=#ff5f00 guibg=#000000
hi CocSnippetVisual ctermfg=202 ctermbg=16


hi CocStrikeThrough guifg=#00ffaf guibg=#000000
hi CocStrikeThrough ctermfg=49 ctermbg=16


hi CocSymbolArray guifg=#af8787 guibg=#000000
hi CocSymbolArray ctermfg=138 ctermbg=16


hi CocSymbolBoolean guifg=#5fd75f guibg=#000000
hi CocSymbolBoolean ctermfg=77 ctermbg=16


hi CocSymbolClass guifg=#d75f00 guibg=#000000
hi CocSymbolClass ctermfg=166 ctermbg=16


hi CocSymbolColor guifg=#87ff5f guibg=#000000
hi CocSymbolColor ctermfg=119 ctermbg=16


hi CocSymbolConstant guifg=#5fff00 guibg=#000000
hi CocSymbolConstant ctermfg=82 ctermbg=16


hi CocSymbolConstructor guifg=#d7af5f guibg=#000000
hi CocSymbolConstructor ctermfg=179 ctermbg=16


hi CocSymbolDefault guifg=#0087af guibg=#000000
hi CocSymbolDefault ctermfg=31 ctermbg=16


hi CocSymbolEnum guifg=#d7af00 guibg=#000000
hi CocSymbolEnum ctermfg=178 ctermbg=16


hi CocSymbolEnumMember guifg=#875f5f guibg=#000000
hi CocSymbolEnumMember ctermfg=95 ctermbg=16


hi CocSymbolEvent guifg=#00ff5f guibg=#000000
hi CocSymbolEvent ctermfg=47 ctermbg=16


hi CocSymbolField guifg=#d70087 guibg=#000000
hi CocSymbolField ctermfg=162 ctermbg=16


hi CocSymbolFile guifg=#d7ff00 guibg=#000000
hi CocSymbolFile ctermfg=190 ctermbg=16


hi CocSymbolFolder guifg=#5fd75f guibg=#000000
hi CocSymbolFolder ctermfg=77 ctermbg=16


hi CocSymbolFunction guifg=#6c6c6c guibg=#000000
hi CocSymbolFunction ctermfg=242 ctermbg=16


hi CocSymbolInterface guifg=#5fd7af guibg=#000000
hi CocSymbolInterface ctermfg=79 ctermbg=16


hi CocSymbolKey guifg=#ff005f guibg=#000000
hi CocSymbolKey ctermfg=197 ctermbg=16


hi CocSymbolKeyword guifg=#5fd787 guibg=#000000
hi CocSymbolKeyword ctermfg=78 ctermbg=16


hi CocSymbolMethod guifg=#6c6c6c guibg=#000000
hi CocSymbolMethod ctermfg=242 ctermbg=16


hi CocSymbolModule guifg=#00d75f guibg=#000000
hi CocSymbolModule ctermfg=41 ctermbg=16


hi CocSymbolNamespace guifg=#d75f5f guibg=#000000
hi CocSymbolNamespace ctermfg=167 ctermbg=16


hi CocSymbolNull guifg=#5fd75f guibg=#000000
hi CocSymbolNull ctermfg=77 ctermbg=16


hi CocSymbolNumber guifg=#87af00 guibg=#000000
hi CocSymbolNumber ctermfg=106 ctermbg=16


hi CocSymbolObject guifg=#5faf5f guibg=#000000
hi CocSymbolObject ctermfg=71 ctermbg=16


hi CocSymbolOperator guifg=#d700af guibg=#000000
hi CocSymbolOperator ctermfg=163 ctermbg=16


hi CocSymbolPackage guifg=#875fff guibg=#000000
hi CocSymbolPackage ctermfg=99 ctermbg=16


hi CocSymbolProperty guifg=#808080 guibg=#000000
hi CocSymbolProperty ctermfg=244 ctermbg=16


hi CocSymbolReference guifg=#808080 guibg=#000000
hi CocSymbolReference ctermfg=244 ctermbg=16


hi CocSymbolSnippet guifg=#af5fd7 guibg=#000000
hi CocSymbolSnippet ctermfg=134 ctermbg=16


hi CocSymbolString guifg=#00ff5f guibg=#000000
hi CocSymbolString ctermfg=47 ctermbg=16


hi CocSymbolStruct guifg=#d7af00 guibg=#000000
hi CocSymbolStruct ctermfg=178 ctermbg=16


hi CocSymbolText guifg=#878787 guibg=#000000
hi CocSymbolText ctermfg=102 ctermbg=16


hi CocSymbolTypeParameter guifg=#5f00d7 guibg=#000000
hi CocSymbolTypeParameter ctermfg=56 ctermbg=16


hi CocSymbolUnit guifg=#87ff00 guibg=#000000
hi CocSymbolUnit ctermfg=118 ctermbg=16


hi CocSymbolValue guifg=#d7875f guibg=#000000
hi CocSymbolValue ctermfg=173 ctermbg=16


hi CocSymbolVariable guifg=#5faf87 guibg=#000000
hi CocSymbolVariable ctermfg=72 ctermbg=16


hi CocTreeDescription guifg=#0087d7 guibg=#000000
hi CocTreeDescription ctermfg=32 ctermbg=16


hi CocTreeOpenClose guifg=#ff00af guibg=#000000
hi CocTreeOpenClose ctermfg=199 ctermbg=16


hi CocTreeSelected guifg=#d7af00 guibg=#000000
hi CocTreeSelected ctermfg=178 ctermbg=16


hi CocTreeTitle guifg=#d700af guibg=#000000
hi CocTreeTitle ctermfg=163 ctermbg=16


hi CocUnderline guifg=#ff875f guibg=#000000
hi CocUnderline ctermfg=209 ctermbg=16


hi CocUnusedHighlight guifg=#87af5f guibg=#000000
hi CocUnusedHighlight ctermfg=107 ctermbg=16


hi CocVirtualText guifg=#afd700 guibg=#000000
hi CocVirtualText ctermfg=148 ctermbg=16


hi CocWarningFloat guifg=#0087d7 guibg=#000000
hi CocWarningFloat ctermfg=32 ctermbg=16


hi CocWarningHighlight guifg=#875f5f guibg=#000000
hi CocWarningHighlight ctermfg=95 ctermbg=16


hi CocWarningSign guifg=#8787d7 guibg=#000000
hi CocWarningSign ctermfg=104 ctermbg=16


hi CocWarningVirtualText guifg=#005fd7 guibg=#000000
hi CocWarningVirtualText ctermfg=26 ctermbg=16


hi ColorColumn guifg=#af0087 guibg=#000000
hi ColorColumn ctermfg=126 ctermbg=16


hi Comment guifg=#af8787 guibg=#000000
hi Comment ctermfg=138 ctermbg=16


hi Conceal guifg=#af8700 guibg=#000000
hi Conceal ctermfg=136 ctermbg=16


hi Conditional guifg=#d7ff00 guibg=#000000
hi Conditional ctermfg=190 ctermbg=16


hi Constant guifg=#00ff5f guibg=#000000
hi Constant ctermfg=47 ctermbg=16


hi CurSearch guifg=#000000 guibg=#ff005f
hi CurSearch ctermfg=16 ctermbg=197


hi CursorColumn guifg=#00ff5f guibg=#000000
hi CursorColumn ctermfg=47 ctermbg=16


hi CursorLine guifg=#af87af guibg=#000000
hi CursorLine ctermfg=139 ctermbg=16


hi CursorLineFold guifg=#ff5f5f guibg=#000000
hi CursorLineFold ctermfg=203 ctermbg=16


hi CursorLineNr guifg=#af5faf guibg=#000000
hi CursorLineNr ctermfg=133 ctermbg=16


hi CursorLineSign guifg=#d75f00 guibg=#000000
hi CursorLineSign ctermfg=166 ctermbg=16


hi Debug guifg=#ff8700 guibg=#000000
hi Debug ctermfg=208 ctermbg=16


hi Define guifg=#d7875f guibg=#000000
hi Define ctermfg=173 ctermbg=16


hi Delimiter guifg=#ff00af guibg=#000000
hi Delimiter ctermfg=199 ctermbg=16


hi DiffAdd guifg=#000000 guibg=#00d7af
hi DiffAdd ctermfg=16 ctermbg=43


hi DiffChange guifg=#000000 guibg=#87af87
hi DiffChange ctermfg=16 ctermbg=108


hi DiffDelete guifg=#000000 guibg=#87af5f
hi DiffDelete ctermfg=16 ctermbg=107


hi DiffText guifg=#000000 guibg=#af5fd7
hi DiffText ctermfg=16 ctermbg=134


hi Directory guifg=#afff00 guibg=#000000
hi Directory ctermfg=154 ctermbg=16


hi EndOfBuffer guifg=#ffaf00 guibg=#000000
hi EndOfBuffer ctermfg=214 ctermbg=16


hi Error guifg=#878787 guibg=#000000
hi Error ctermfg=102 ctermbg=16


hi ErrorMsg guifg=#5fd75f guibg=#000000
hi ErrorMsg ctermfg=77 ctermbg=16


hi Exception guifg=#5f5faf guibg=#000000
hi Exception ctermfg=61 ctermbg=16


hi Float guifg=#d70087 guibg=#000000
hi Float ctermfg=162 ctermbg=16


hi FoldColumn guifg=#87875f guibg=#000000
hi FoldColumn ctermfg=101 ctermbg=16


hi Folded guifg=#d78700 guibg=#000000
hi Folded ctermfg=172 ctermbg=16


hi Function guifg=#00d7d7 guibg=#000000
hi Function ctermfg=44 ctermbg=16


hi Identifier guifg=#87ff00 guibg=#000000
hi Identifier ctermfg=118 ctermbg=16


hi Ignore guifg=#5fafaf guibg=#000000
hi Ignore ctermfg=73 ctermbg=16


hi IncSearch guifg=#000000 guibg=#875fff
hi IncSearch ctermfg=16 ctermbg=99


hi Include guifg=#d70087 guibg=#000000
hi Include ctermfg=162 ctermbg=16


hi Keyword guifg=#d7af00 guibg=#000000
hi Keyword ctermfg=178 ctermbg=16


hi Label guifg=#d75faf guibg=#000000
hi Label ctermfg=169 ctermbg=16


hi LineNr guifg=#87d75f guibg=#000000
hi LineNr ctermfg=113 ctermbg=16


hi Macro guifg=#0087ff guibg=#000000
hi Macro ctermfg=33 ctermbg=16


hi MatchParen guifg=#af5fd7 guibg=#000000
hi MatchParen ctermfg=134 ctermbg=16


hi ModeMsg guifg=#af5faf guibg=#000000
hi ModeMsg ctermfg=133 ctermbg=16


hi MoreMsg guifg=#00afaf guibg=#000000
hi MoreMsg ctermfg=37 ctermbg=16


hi NonText guifg=#ffaf00 guibg=#000000
hi NonText ctermfg=214 ctermbg=16


hi Normal guifg=#ffffff guibg=#ffffff
hi Normal ctermfg=231 ctermbg=16


hi Number guifg=#d7875f guibg=#000000
hi Number ctermfg=173 ctermbg=16


hi Operator guifg=#af00ff guibg=#000000
hi Operator ctermfg=129 ctermbg=16


hi Pmenu guifg=#5f875f guibg=#000000
hi Pmenu ctermfg=65 ctermbg=16


hi PmenuExtra guifg=#ffaf00 guibg=#000000
hi PmenuExtra ctermfg=214 ctermbg=16


hi PmenuExtraSel guifg=#d75f00 guibg=#000000
hi PmenuExtraSel ctermfg=166 ctermbg=16


hi PmenuKind guifg=#00afff guibg=#000000
hi PmenuKind ctermfg=39 ctermbg=16


hi PmenuKindSel guifg=#d700af guibg=#000000
hi PmenuKindSel ctermfg=163 ctermbg=16


hi PmenuSbar guifg=#5fd75f guibg=#000000
hi PmenuSbar ctermfg=77 ctermbg=16


hi PmenuSel guifg=#8700d7 guibg=#000000
hi PmenuSel ctermfg=92 ctermbg=16


hi PmenuThumb guifg=#5fafd7 guibg=#000000
hi PmenuThumb ctermfg=74 ctermbg=16


hi PreCondit guifg=#00d7af guibg=#000000
hi PreCondit ctermfg=43 ctermbg=16


hi PreProc guifg=#d75f5f guibg=#000000
hi PreProc ctermfg=167 ctermbg=16


hi Question guifg=#af875f guibg=#000000
hi Question ctermfg=137 ctermbg=16


hi QuickFixLine guifg=#5fff5f guibg=#000000
hi QuickFixLine ctermfg=83 ctermbg=16


hi Removed guifg=#af875f guibg=#000000
hi Removed ctermfg=137 ctermbg=16


hi Repeat guifg=#005fd7 guibg=#000000
hi Repeat ctermfg=26 ctermbg=16


hi Search guifg=#000000 guibg=#d78700
hi Search ctermfg=16 ctermbg=172


hi SignColumn guifg=#af00af guibg=#000000
hi SignColumn ctermfg=127 ctermbg=16


hi Special guifg=#af00af guibg=#000000
hi Special ctermfg=127 ctermbg=16


hi SpecialChar guifg=#afaf87 guibg=#000000
hi SpecialChar ctermfg=144 ctermbg=16


hi SpecialComment guifg=#00ff5f guibg=#000000
hi SpecialComment ctermfg=47 ctermbg=16


hi SpecialKey guifg=#00af87 guibg=#000000
hi SpecialKey ctermfg=36 ctermbg=16


hi SpellBad guifg=#949494 guibg=#000000
hi SpellBad ctermfg=246 ctermbg=16


hi SpellCap guifg=#5fff87 guibg=#000000
hi SpellCap ctermfg=84 ctermbg=16


hi SpellLocal guifg=#5fafd7 guibg=#000000
hi SpellLocal ctermfg=74 ctermbg=16


hi SpellRare guifg=#ffd700 guibg=#000000
hi SpellRare ctermfg=220 ctermbg=16


hi Statement guifg=#af5fd7 guibg=#000000
hi Statement ctermfg=134 ctermbg=16


hi StatusLine guifg=#ff5f00 guibg=#000000
hi StatusLine ctermfg=202 ctermbg=16


hi StatusLineNC guifg=#af8700 guibg=#000000
hi StatusLineNC ctermfg=136 ctermbg=16


hi StorageClass guifg=#5fff00 guibg=#000000
hi StorageClass ctermfg=82 ctermbg=16


hi String guifg=#0087ff guibg=#000000
hi String ctermfg=33 ctermbg=16


hi Structure guifg=#ff00af guibg=#000000
hi Structure ctermfg=199 ctermbg=16


hi TabLine guifg=#87ff5f guibg=#000000
hi TabLine ctermfg=119 ctermbg=16


hi TabLineFill guifg=#af8787 guibg=#000000
hi TabLineFill ctermfg=138 ctermbg=16


hi TabLineSel guifg=#afff00 guibg=#000000
hi TabLineSel ctermfg=154 ctermbg=16


hi Tag guifg=#af8700 guibg=#000000
hi Tag ctermfg=136 ctermbg=16


hi Title guifg=#87ff00 guibg=#000000
hi Title ctermfg=118 ctermbg=16


hi Todo guifg=#5f87ff guibg=#000000
hi Todo ctermfg=69 ctermbg=16


hi ToolbarButton guifg=#87afaf guibg=#000000
hi ToolbarButton ctermfg=109 ctermbg=16


hi ToolbarLine guifg=#d700ff guibg=#000000
hi ToolbarLine ctermfg=165 ctermbg=16


hi Type guifg=#005fd7 guibg=#000000
hi Type ctermfg=26 ctermbg=16


hi Typedef guifg=#af00af guibg=#000000
hi Typedef ctermfg=127 ctermbg=16


hi Underlined guifg=#875fd7 guibg=#000000
hi Underlined ctermfg=98 ctermbg=16


hi VertSplit guifg=#0087ff guibg=#000000
hi VertSplit ctermfg=33 ctermbg=16


hi Visual guifg=#ff5f5f guibg=#000000
hi Visual ctermfg=203 ctermbg=16


hi WarningMsg guifg=#5f5faf guibg=#000000
hi WarningMsg ctermfg=61 ctermbg=16


hi WildMenu guifg=#d700d7 guibg=#000000
hi WildMenu ctermfg=164 ctermbg=16


hi italics guifg=#87d787 guibg=#000000
hi italics ctermfg=114 ctermbg=16


hi letter_a guifg=#875fd7 guibg=#000000
hi letter_a ctermfg=98 ctermbg=16


hi quixote guifg=#5f87af guibg=#000000
hi quixote ctermfg=67 ctermbg=16


hi quote guifg=#00afd7 guibg=#000000
hi quote ctermfg=38 ctermbg=16


hi quoteerror guifg=#d700d7 guibg=#000000
hi quoteerror ctermfg=164 ctermbg=16


hi vim9Comment guifg=#8700af guibg=#000000
hi vim9Comment ctermfg=91 ctermbg=16


hi vim9CommentTitle guifg=#d78700 guibg=#000000
hi vim9CommentTitle ctermfg=172 ctermbg=16


hi vim9KeymapLineComment guifg=#d78700 guibg=#000000
hi vim9KeymapLineComment ctermfg=172 ctermbg=16


hi vim9LineComment guifg=#5fff87 guibg=#000000
hi vim9LineComment ctermfg=84 ctermbg=16


hi vim9Vim9Script guifg=#d700ff guibg=#000000
hi vim9Vim9Script ctermfg=165 ctermbg=16


hi vim9Vim9ScriptArg guifg=#00ffaf guibg=#000000
hi vim9Vim9ScriptArg ctermfg=49 ctermbg=16


hi vimAbb guifg=#afff00 guibg=#000000
hi vimAbb ctermfg=154 ctermbg=16


hi vimAddress guifg=#87d787 guibg=#000000
hi vimAddress ctermfg=114 ctermbg=16


hi vimAugroupBang guifg=#87875f guibg=#000000
hi vimAugroupBang ctermfg=101 ctermbg=16


hi vimAugroupError guifg=#875fff guibg=#000000
hi vimAugroupError ctermfg=99 ctermbg=16


hi vimAugroupKey guifg=#8700ff guibg=#000000
hi vimAugroupKey ctermfg=93 ctermbg=16


hi vimAutoCmd guifg=#5fd787 guibg=#000000
hi vimAutoCmd ctermfg=78 ctermbg=16


hi vimAutoCmdMod guifg=#ff5f5f guibg=#000000
hi vimAutoCmdMod ctermfg=203 ctermbg=16


hi vimAutoEvent guifg=#afd75f guibg=#000000
hi vimAutoEvent ctermfg=149 ctermbg=16


hi vimBang guifg=#87d700 guibg=#000000
hi vimBang ctermfg=112 ctermbg=16


hi vimBehave guifg=#8787af guibg=#000000
hi vimBehave ctermfg=103 ctermbg=16


hi vimBehaveBang guifg=#d700ff guibg=#000000
hi vimBehaveBang ctermfg=165 ctermbg=16


hi vimBehaveError guifg=#afaf5f guibg=#000000
hi vimBehaveError ctermfg=143 ctermbg=16


hi vimBehaveModel guifg=#5faf87 guibg=#000000
hi vimBehaveModel ctermfg=72 ctermbg=16


hi vimBracket guifg=#af00ff guibg=#000000
hi vimBracket ctermfg=129 ctermbg=16


hi vimBufnrWarn guifg=#ff5f5f guibg=#000000
hi vimBufnrWarn ctermfg=203 ctermbg=16


hi vimCmplxRepeat guifg=#00ff87 guibg=#000000
hi vimCmplxRepeat ctermfg=48 ctermbg=16


hi vimCollClassErr guifg=#8700af guibg=#000000
hi vimCollClassErr ctermfg=91 ctermbg=16


hi vimCommand guifg=#ffd700 guibg=#000000
hi vimCommand ctermfg=220 ctermbg=16


hi vimComment guifg=#00ff5f guibg=#000000
hi vimComment ctermfg=47 ctermbg=16


hi vimCommentString guifg=#87af5f guibg=#000000
hi vimCommentString ctermfg=107 ctermbg=16


hi vimCommentTitle guifg=#ffd700 guibg=#000000
hi vimCommentTitle ctermfg=220 ctermbg=16


hi vimCondHL guifg=#00ff87 guibg=#000000
hi vimCondHL ctermfg=48 ctermbg=16


hi vimConst guifg=#af00af guibg=#000000
hi vimConst ctermfg=127 ctermbg=16


hi vimContinue guifg=#00ffd7 guibg=#000000
hi vimContinue ctermfg=50 ctermbg=16


hi vimContinueComment guifg=#d7ff00 guibg=#000000
hi vimContinueComment ctermfg=190 ctermbg=16


hi vimCtrlChar guifg=#ff005f guibg=#000000
hi vimCtrlChar ctermfg=197 ctermbg=16


hi vimDefComment guifg=#af5f5f guibg=#000000
hi vimDefComment ctermfg=131 ctermbg=16


hi vimDefKey guifg=#5f5faf guibg=#000000
hi vimDefKey ctermfg=61 ctermbg=16


hi vimDefParam guifg=#d7af5f guibg=#000000
hi vimDefParam ctermfg=179 ctermbg=16


hi vimEcho guifg=#8a8a8a guibg=#000000
hi vimEcho ctermfg=245 ctermbg=16


hi vimEchohl guifg=#808080 guibg=#000000
hi vimEchohl ctermfg=244 ctermbg=16


hi vimEchohlNone guifg=#d75f87 guibg=#000000
hi vimEchohlNone ctermfg=168 ctermbg=16


hi vimElseIfErr guifg=#8787af guibg=#000000
hi vimElseIfErr ctermfg=103 ctermbg=16


hi vimEmbedError guifg=#af00d7 guibg=#000000
hi vimEmbedError ctermfg=128 ctermbg=16


hi vimEnddef guifg=#00ffaf guibg=#000000
hi vimEnddef ctermfg=49 ctermbg=16


hi vimEndfunction guifg=#5fafd7 guibg=#000000
hi vimEndfunction ctermfg=74 ctermbg=16


hi vimEnvvar guifg=#5fd7af guibg=#000000
hi vimEnvvar ctermfg=79 ctermbg=16


hi vimErrSetting guifg=#d7d700 guibg=#000000
hi vimErrSetting ctermfg=184 ctermbg=16


hi vimError guifg=#5fd700 guibg=#000000
hi vimError ctermfg=76 ctermbg=16


hi vimEscape guifg=#ff5f5f guibg=#000000
hi vimEscape ctermfg=203 ctermbg=16


hi vimFBVar guifg=#d700af guibg=#000000
hi vimFBVar ctermfg=163 ctermbg=16


hi vimFTCmd guifg=#00d75f guibg=#000000
hi vimFTCmd ctermfg=41 ctermbg=16


hi vimFTError guifg=#d75f5f guibg=#000000
hi vimFTError ctermfg=167 ctermbg=16


hi vimFTOption guifg=#af5faf guibg=#000000
hi vimFTOption ctermfg=133 ctermbg=16


hi vimFgBgAttrib guifg=#00afff guibg=#000000
hi vimFgBgAttrib ctermfg=39 ctermbg=16


hi vimFor guifg=#d78700 guibg=#000000
hi vimFor ctermfg=172 ctermbg=16


hi vimFunc guifg=#ff5f87 guibg=#000000
hi vimFunc ctermfg=204 ctermbg=16


hi vimFuncBang guifg=#af00af guibg=#000000
hi vimFuncBang ctermfg=127 ctermbg=16


hi vimFuncComment guifg=#5fafaf guibg=#000000
hi vimFuncComment ctermfg=73 ctermbg=16


hi vimFuncEcho guifg=#0087af guibg=#000000
hi vimFuncEcho ctermfg=31 ctermbg=16


hi vimFuncKey guifg=#875fff guibg=#000000
hi vimFuncKey ctermfg=99 ctermbg=16


hi vimFuncMod guifg=#d7005f guibg=#000000
hi vimFuncMod ctermfg=161 ctermbg=16


hi vimFuncName guifg=#00ff5f guibg=#000000
hi vimFuncName ctermfg=47 ctermbg=16


hi vimFuncParam guifg=#d700d7 guibg=#000000
hi vimFuncParam ctermfg=164 ctermbg=16


hi vimFuncParamEquals guifg=#005fd7 guibg=#000000
hi vimFuncParamEquals ctermfg=26 ctermbg=16


hi vimFuncSID guifg=#00ff87 guibg=#000000
hi vimFuncSID ctermfg=48 ctermbg=16


hi vimFuncVar guifg=#d70087 guibg=#000000
hi vimFuncVar ctermfg=162 ctermbg=16


hi vimFunctionError guifg=#5faf87 guibg=#000000
hi vimFunctionError ctermfg=72 ctermbg=16


hi vimGroup guifg=#af5fd7 guibg=#000000
hi vimGroup ctermfg=134 ctermbg=16


hi vimGroupAdd guifg=#00d7d7 guibg=#000000
hi vimGroupAdd ctermfg=44 ctermbg=16


hi vimGroupName guifg=#875f87 guibg=#000000
hi vimGroupName ctermfg=96 ctermbg=16


hi vimGroupRem guifg=#808080 guibg=#000000
hi vimGroupRem ctermfg=244 ctermbg=16


hi vimGroupSpecial guifg=#5faf5f guibg=#000000
hi vimGroupSpecial ctermfg=71 ctermbg=16


hi vimHLGroup guifg=#00af87 guibg=#000000
hi vimHLGroup ctermfg=36 ctermbg=16


hi vimHiAttrib guifg=#0087af guibg=#000000
hi vimHiAttrib ctermfg=31 ctermbg=16


hi vimHiAttribList guifg=#5fff00 guibg=#000000
hi vimHiAttribList ctermfg=82 ctermbg=16


hi vimHiBang guifg=#5fd7af guibg=#000000
hi vimHiBang ctermfg=79 ctermbg=16


hi vimHiCTerm guifg=#005fd7 guibg=#000000
hi vimHiCTerm ctermfg=26 ctermbg=16


hi vimHiClear guifg=#d78787 guibg=#000000
hi vimHiClear ctermfg=174 ctermbg=16


hi vimHiCtermColor guifg=#af875f guibg=#000000
hi vimHiCtermColor ctermfg=137 ctermbg=16


hi vimHiCtermError guifg=#87afaf guibg=#000000
hi vimHiCtermError ctermfg=109 ctermbg=16


hi vimHiCtermFgBg guifg=#875f87 guibg=#000000
hi vimHiCtermFgBg ctermfg=96 ctermbg=16


hi vimHiCtermfont guifg=#afaf87 guibg=#000000
hi vimHiCtermfont ctermfg=144 ctermbg=16


hi vimHiCtermul guifg=#9e9e9e guibg=#000000
hi vimHiCtermul ctermfg=247 ctermbg=16


hi vimHiGroup guifg=#87af87 guibg=#000000
hi vimHiGroup ctermfg=108 ctermbg=16


hi vimHiGui guifg=#00ff5f guibg=#000000
hi vimHiGui ctermfg=47 ctermbg=16


hi vimHiGuiFgBg guifg=#5f8787 guibg=#000000
hi vimHiGuiFgBg ctermfg=66 ctermbg=16


hi vimHiGuiFont guifg=#d7005f guibg=#000000
hi vimHiGuiFont ctermfg=161 ctermbg=16


hi vimHiGuiRgb guifg=#d78700 guibg=#000000
hi vimHiGuiRgb ctermfg=172 ctermbg=16


hi vimHiKeyError guifg=#5f5faf guibg=#000000
hi vimHiKeyError ctermfg=61 ctermbg=16


hi vimHiNmbr guifg=#af00ff guibg=#000000
hi vimHiNmbr ctermfg=129 ctermbg=16


hi vimHiStartStop guifg=#ff8700 guibg=#000000
hi vimHiStartStop ctermfg=208 ctermbg=16


hi vimHiTerm guifg=#8787af guibg=#000000
hi vimHiTerm ctermfg=103 ctermbg=16


hi vimHighlight guifg=#87ff00 guibg=#000000
hi vimHighlight ctermfg=118 ctermbg=16


hi vimInsert guifg=#5f5faf guibg=#000000
hi vimInsert ctermfg=61 ctermbg=16


hi vimIskSep guifg=#8700d7 guibg=#000000
hi vimIskSep ctermfg=92 ctermbg=16


hi vimKeymapLineComment guifg=#5f87ff guibg=#000000
hi vimKeymapLineComment ctermfg=69 ctermbg=16


hi vimKeymapTailComment guifg=#5f875f guibg=#000000
hi vimKeymapTailComment ctermfg=65 ctermbg=16


hi vimLet guifg=#878787 guibg=#000000
hi vimLet ctermfg=102 ctermbg=16


hi vimLetHereDoc guifg=#5f5fd7 guibg=#000000
hi vimLetHereDoc ctermfg=62 ctermbg=16


hi vimLetHereDocStart guifg=#af875f guibg=#000000
hi vimLetHereDocStart ctermfg=137 ctermbg=16


hi vimLetHereDocStop guifg=#0087ff guibg=#000000
hi vimLetHereDocStop ctermfg=33 ctermbg=16


hi vimLetRegister guifg=#00afaf guibg=#000000
hi vimLetRegister ctermfg=37 ctermbg=16


hi vimLineComment guifg=#5f5faf guibg=#000000
hi vimLineComment ctermfg=61 ctermbg=16


hi vimMap guifg=#005fd7 guibg=#000000
hi vimMap ctermfg=26 ctermbg=16


hi vimMapBang guifg=#ff5f87 guibg=#000000
hi vimMapBang ctermfg=204 ctermbg=16


hi vimMapMod guifg=#5fd75f guibg=#000000
hi vimMapMod ctermfg=77 ctermbg=16


hi vimMapModErr guifg=#00d75f guibg=#000000
hi vimMapModErr ctermfg=41 ctermbg=16


hi vimMapModKey guifg=#afaf5f guibg=#000000
hi vimMapModKey ctermfg=143 ctermbg=16


hi vimMark guifg=#875f5f guibg=#000000
hi vimMark ctermfg=95 ctermbg=16


hi vimMarkNumber guifg=#d75f00 guibg=#000000
hi vimMarkNumber ctermfg=166 ctermbg=16


hi vimMenu guifg=#5fafd7 guibg=#000000
hi vimMenu ctermfg=74 ctermbg=16


hi vimMenuBang guifg=#af8700 guibg=#000000
hi vimMenuBang ctermfg=136 ctermbg=16


hi vimMenuClear guifg=#8700ff guibg=#000000
hi vimMenuClear ctermfg=93 ctermbg=16


hi vimMenuMod guifg=#d75faf guibg=#000000
hi vimMenuMod ctermfg=169 ctermbg=16


hi vimMenuName guifg=#afaf5f guibg=#000000
hi vimMenuName ctermfg=143 ctermbg=16


hi vimMenuNotation guifg=#d75f5f guibg=#000000
hi vimMenuNotation ctermfg=167 ctermbg=16


hi vimMenuPriority guifg=#00d7d7 guibg=#000000
hi vimMenuPriority ctermfg=44 ctermbg=16


hi vimMenuStatus guifg=#af5f5f guibg=#000000
hi vimMenuStatus ctermfg=131 ctermbg=16


hi vimMenutranslateComment guifg=#af00af guibg=#000000
hi vimMenutranslateComment ctermfg=127 ctermbg=16


hi vimMethodName guifg=#d700ff guibg=#000000
hi vimMethodName ctermfg=165 ctermbg=16


hi vimMtchComment guifg=#0087d7 guibg=#000000
hi vimMtchComment ctermfg=32 ctermbg=16


hi vimNorm guifg=#5f8787 guibg=#000000
hi vimNorm ctermfg=66 ctermbg=16


hi vimNotFunc guifg=#87af5f guibg=#000000
hi vimNotFunc ctermfg=107 ctermbg=16


hi vimNotPatSep guifg=#87ff5f guibg=#000000
hi vimNotPatSep ctermfg=119 ctermbg=16


hi vimNotation guifg=#af0087 guibg=#000000
hi vimNotation ctermfg=126 ctermbg=16


hi vimNumber guifg=#d7af00 guibg=#000000
hi vimNumber ctermfg=178 ctermbg=16


hi vimOper guifg=#0087ff guibg=#000000
hi vimOper ctermfg=33 ctermbg=16


hi vimOperError guifg=#0087d7 guibg=#000000
hi vimOperError ctermfg=32 ctermbg=16


hi vimOption guifg=#0087d7 guibg=#000000
hi vimOption ctermfg=32 ctermbg=16


hi vimParenSep guifg=#afd700 guibg=#000000
hi vimParenSep ctermfg=148 ctermbg=16


hi vimPatSep guifg=#afd700 guibg=#000000
hi vimPatSep ctermfg=148 ctermbg=16


hi vimPatSepErr guifg=#d700af guibg=#000000
hi vimPatSepErr ctermfg=163 ctermbg=16


hi vimPatSepR guifg=#87af5f guibg=#000000
hi vimPatSepR ctermfg=107 ctermbg=16


hi vimPatSepZ guifg=#5f5fff guibg=#000000
hi vimPatSepZ ctermfg=63 ctermbg=16


hi vimPatSepZone guifg=#8787af guibg=#000000
hi vimPatSepZone ctermfg=103 ctermbg=16


hi vimPattern guifg=#00af87 guibg=#000000
hi vimPattern ctermfg=36 ctermbg=16


hi vimPlainMark guifg=#00afff guibg=#000000
hi vimPlainMark ctermfg=39 ctermbg=16


hi vimPlainRegister guifg=#ff875f guibg=#000000
hi vimPlainRegister ctermfg=209 ctermbg=16


hi vimRegister guifg=#8700d7 guibg=#000000
hi vimRegister ctermfg=92 ctermbg=16


hi vimScriptDelim guifg=#87ff00 guibg=#000000
hi vimScriptDelim ctermfg=118 ctermbg=16


hi vimSearch guifg=#000000 guibg=#5fafaf
hi vimSearch ctermfg=16 ctermbg=73


hi vimSearchDelim guifg=#000000 guibg=#ff5f5f
hi vimSearchDelim ctermfg=16 ctermbg=203


hi vimSep guifg=#af5f87 guibg=#000000
hi vimSep ctermfg=132 ctermbg=16


hi vimSetMod guifg=#6c6c6c guibg=#000000
hi vimSetMod ctermfg=242 ctermbg=16


hi vimSetSep guifg=#d75f87 guibg=#000000
hi vimSetSep ctermfg=168 ctermbg=16


hi vimSetString guifg=#808080 guibg=#000000
hi vimSetString ctermfg=244 ctermbg=16


hi vimSpecFile guifg=#87875f guibg=#000000
hi vimSpecFile ctermfg=101 ctermbg=16


hi vimSpecFileMod guifg=#af5fd7 guibg=#000000
hi vimSpecFileMod ctermfg=134 ctermbg=16


hi vimSpecial guifg=#5f5f87 guibg=#000000
hi vimSpecial ctermfg=60 ctermbg=16


hi vimString guifg=#afaf00 guibg=#000000
hi vimString ctermfg=142 ctermbg=16


hi vimStringCont guifg=#00d7ff guibg=#000000
hi vimStringCont ctermfg=45 ctermbg=16


hi vimStringEnd guifg=#00d7d7 guibg=#000000
hi vimStringEnd ctermfg=44 ctermbg=16


hi vimStringInterpolationBrace guifg=#00afaf guibg=#000000
hi vimStringInterpolationBrace ctermfg=37 ctermbg=16


hi vimSubst guifg=#d7005f guibg=#000000
hi vimSubst ctermfg=161 ctermbg=16


hi vimSubst1 guifg=#875fd7 guibg=#000000
hi vimSubst1 ctermfg=98 ctermbg=16


hi vimSubstDelim guifg=#af5f5f guibg=#000000
hi vimSubstDelim ctermfg=131 ctermbg=16


hi vimSubstFlagErr guifg=#00ffaf guibg=#000000
hi vimSubstFlagErr ctermfg=49 ctermbg=16


hi vimSubstFlags guifg=#0087d7 guibg=#000000
hi vimSubstFlags ctermfg=32 ctermbg=16


hi vimSubstSubstr guifg=#ff5f5f guibg=#000000
hi vimSubstSubstr ctermfg=203 ctermbg=16


hi vimSubstTwoBS guifg=#af8787 guibg=#000000
hi vimSubstTwoBS ctermfg=138 ctermbg=16


hi vimSynCase guifg=#8700ff guibg=#000000
hi vimSynCase ctermfg=93 ctermbg=16


hi vimSynCaseError guifg=#5f87ff guibg=#000000
hi vimSynCaseError ctermfg=69 ctermbg=16


hi vimSynCchar guifg=#0087ff guibg=#000000
hi vimSynCchar ctermfg=33 ctermbg=16


hi vimSynCcharValue guifg=#ff5f00 guibg=#000000
hi vimSynCcharValue ctermfg=202 ctermbg=16


hi vimSynContains guifg=#af875f guibg=#000000
hi vimSynContains ctermfg=137 ctermbg=16


hi vimSynError guifg=#0087ff guibg=#000000
hi vimSynError ctermfg=33 ctermbg=16


hi vimSynFoldMethod guifg=#ff0087 guibg=#000000
hi vimSynFoldMethod ctermfg=198 ctermbg=16


hi vimSynFoldMethodError guifg=#5fafd7 guibg=#000000
hi vimSynFoldMethodError ctermfg=74 ctermbg=16


hi vimSynKeyContainedin guifg=#5f875f guibg=#000000
hi vimSynKeyContainedin ctermfg=65 ctermbg=16


hi vimSynKeyOpt guifg=#afaf00 guibg=#000000
hi vimSynKeyOpt ctermfg=142 ctermbg=16


hi vimSynMtchGrp guifg=#00d787 guibg=#000000
hi vimSynMtchGrp ctermfg=42 ctermbg=16


hi vimSynMtchOpt guifg=#878787 guibg=#000000
hi vimSynMtchOpt ctermfg=102 ctermbg=16


hi vimSynNextgroup guifg=#00afaf guibg=#000000
hi vimSynNextgroup ctermfg=37 ctermbg=16


hi vimSynNotPatRange guifg=#5fff5f guibg=#000000
hi vimSynNotPatRange ctermfg=83 ctermbg=16


hi vimSynOption guifg=#5f5f87 guibg=#000000
hi vimSynOption ctermfg=60 ctermbg=16


hi vimSynPatRange guifg=#8787d7 guibg=#000000
hi vimSynPatRange ctermfg=104 ctermbg=16


hi vimSynReg guifg=#6c6c6c guibg=#000000
hi vimSynReg ctermfg=242 ctermbg=16


hi vimSynRegOpt guifg=#875faf guibg=#000000
hi vimSynRegOpt ctermfg=97 ctermbg=16


hi vimSynRegPat guifg=#8700af guibg=#000000
hi vimSynRegPat ctermfg=91 ctermbg=16


hi vimSynType guifg=#ff875f guibg=#000000
hi vimSynType ctermfg=209 ctermbg=16

hi yamlFlowString guifg=#ff875f guibg=#000000
hi yamlFlowString ctermfg=209 ctermbg=16


hi vimSyncC guifg=#87d75f guibg=#000000
hi vimSyncC ctermfg=113 ctermbg=16


hi vimSyncError guifg=#87ff00 guibg=#000000
hi vimSyncError ctermfg=118 ctermbg=16


hi vimSyncGroup guifg=#5fd75f guibg=#000000
hi vimSyncGroup ctermfg=77 ctermbg=16


hi vimSyncGroupName guifg=#87d787 guibg=#000000
hi vimSyncGroupName ctermfg=114 ctermbg=16


hi vimSyncKey guifg=#5fafaf guibg=#000000
hi vimSyncKey ctermfg=73 ctermbg=16


hi vimSyncNone guifg=#af00ff guibg=#000000
hi vimSyncNone ctermfg=129 ctermbg=16


hi vimSyntax guifg=#00afaf guibg=#000000
hi vimSyntax ctermfg=37 ctermbg=16

hi yamlBlocKMappingKey guifg=#00afaf guibg=#000000
hi yamlBlockMappingKey ctermfg=37 ctermbg=16


hi vimTodo guifg=#d7af5f guibg=#000000
hi vimTodo ctermfg=179 ctermbg=16


hi vimType guifg=#87d787 guibg=#000000
hi vimType ctermfg=114 ctermbg=16


hi vimUnlet guifg=#808080 guibg=#000000
hi vimUnlet ctermfg=244 ctermbg=16


hi vimUnletBang guifg=#878787 guibg=#000000
hi vimUnletBang ctermfg=102 ctermbg=16


hi vimUnmap guifg=#00ffaf guibg=#000000
hi vimUnmap ctermfg=49 ctermbg=16


hi vimUserAttrb guifg=#8700ff guibg=#000000
hi vimUserAttrb ctermfg=93 ctermbg=16


hi vimUserAttrbCmplt guifg=#5fd787 guibg=#000000
hi vimUserAttrbCmplt ctermfg=78 ctermbg=16


hi vimUserAttrbCmpltFunc guifg=#00d787 guibg=#000000
hi vimUserAttrbCmpltFunc ctermfg=42 ctermbg=16


hi vimUserAttrbError guifg=#00af87 guibg=#000000
hi vimUserAttrbError ctermfg=36 ctermbg=16


hi vimUserAttrbKey guifg=#87875f guibg=#000000
hi vimUserAttrbKey ctermfg=101 ctermbg=16


hi vimUserCmdError guifg=#00ffd7 guibg=#000000
hi vimUserCmdError ctermfg=50 ctermbg=16

hi shOption guifg=#00ffd7 guibg=#000000
hi shOption ctermfg=50 ctermbg=16


hi vimUserCommand guifg=#8700af guibg=#000000
hi vimUserCommand ctermfg=91 ctermbg=16


hi vimVar guifg=#00d7d7 guibg=#000000
hi vimVar ctermfg=44 ctermbg=16

hi shOperator guifg=#00d7d7 guibg=#000000
hi shOperator ctermfg=44 ctermbg=16


hi vimWarn guifg=#8787af guibg=#000000
hi vimWarn ctermfg=103 ctermbg=16

hi shParen guifg=#8787af guibg=#000000
hi shParen ctermfg=103 ctermbg=16
