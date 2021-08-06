#!/usr/bin/perl
use strict;
use FileHandle;
use Lingua::EN::Numbers qw(num2en num2en_ordinal);

my %fonts = ();
sub addfont {
    my $f = shift;
    my @k = keys %fonts;
    $fonts{$f} = $#k+1;
}

my $use_toc = 0;

######################################
# Configurables
######################################

my $center_scene_brk = 1;
my $mm = 56.692913386/1440.0; # twips per millimeter
my $inch = 1440.0; # twips per inch
my $smartquote = 0;
my $emdash = 0;
my $ellipsis = 0;
my $font_size = 12; 
my $spacing = 1; 
my $paperw = 6.0; # page width
my $paperh = 9.0; # page height
#my $paperw = 4.25;
#my $paperh = 6.875;
my $italics_on = 1;
addfont("Courier New");
addfont("Times New Roman");
addfont("Palatino Linotype");
addfont("Papyrus");
my $font = "Times New Roman";
my $chapters_on = 0;
my $chapters_brief = 0;
my $notes_on = 0;
my $chapter_lines = 0;
my $gutter = 0.5;
my $indent = 0.25;
$main::tighten = "";
my ($marginl,$marginr,$margint,$marginb) = 
   (     0.5,     0.5,     0.5,     0.5);
my $bold_chapters = 1;
my $mode = "submit";
my $scenebrk = "#";

######################################
#Commands:
# <i> .. </i0>
# <chapter>
# <nochapter>
# <end>
# <note="note">
# <header>
# <sect>
# <sect no-par>
# <scene>
# <line="..." right="...">
# <set-page-num={num}>
# <blank-lines={num}>
######################################

sub setmode {
  my $mode = shift;
  if($mode eq "submit") {
    print "SUBMIT MODE ON\n";
    $chapters_on = 1;
    $italics_on = 0;
    $spacing = 2;
    $font_size = 12;
    $font = "Times New Roman";
    $notes_on = 0;
    $bold_chapters = 0;
    $chapter_lines=15;
    $paperw = 8.5;
    $paperh = 11.0;
    $center_scene_brk = 0;
    ($marginl,$marginr,$margint,$marginb) = 
    (     1.0,     1.0,     1.0,     1.0);
  } elsif($mode eq "submit2") {
    print "SUBMIT MODE ON\n";
    $chapters_on = 0;
    $chapter_lines=15;
    $italics_on = 1;
    $spacing = 2;
    $font_size = 12;
    $font = "Times New Roman";
    $notes_on = 0;
    $bold_chapters = 0;
    $paperw = 8.5;
    $paperh = 11.0;
    ($marginl,$marginr,$margint,$marginb) = 
    (     1.0,     1.0,     1.0,     1.0);
  } elsif($mode eq "submit-andromeda") {
    print "SUBMIT MODE ON\n";
    $chapters_on = 0;
    $indent = 5.0*$mm;
    printf("indent=%f\n",$indent);
    $scenebrk = "* * *";
    $italics_on = 0;
    $ellipsis = 1;
    $emdash = 1;
    $spacing = 2;
    $font_size = 12;
    $font = "Times New Roman";
    $notes_on = 0;
    $bold_chapters = 0;
    $paperw = 8.5;
    $paperh = 11.0;
    ($marginl,$marginr,$margint,$marginb) = 
    (     1.0,     1.0,     1.0,     1.0);
  } elsif($mode eq "lightspeed") {
    print "SUBMIT MODE ON\n";
    $chapters_on = 0;
    $italics_on = 0;
    $spacing = 1;
    $font_size = 12;
    $font = "Courier New";
    $notes_on = 0;
    $bold_chapters = 0;
  } elsif($mode eq "mysterical") {
    $chapters_on = 1;
    $italics_on = 1;
    $spacing = 1;
    $font_size = 12;
    $font = "Times New Roman";
    $notes_on = 0;
    $bold_chapters = 0;
    $indent = 0;
  } elsif($mode eq "story") {
    print "STORY MODE ON\n";
    $chapters_on = 1;
    $italics_on = 1;
    $spacing = 2;
    $font_size = 12;
    $font = "Courier New";
    $notes_on = 0;
    $bold_chapters = 0;
  } elsif($mode eq "edit") {
    print "EDIT MODE ON\n";
    $chapters_on = 1;
    $italics_on = 1;
    $spacing = 2;
    $font_size = 12;
    $font = "Times New Roman";
    $notes_on = 1;
    $bold_chapters = 1;
  } elsif($mode eq "dense") {
    print "DENSE MODE ON\n";
    $chapters_on = 1;
    $chapters_brief = 1;
    $italics_on = 1;
    $spacing = 1;
    $font_size = 12;
    $font = "Palatino Linotype";#Times New Roman";
    $notes_on = 0;
    $bold_chapters = 1;
    $paperw = 6;
    $paperh = 9;
    #($marginl,$marginr,$margint,$marginb) = 
    #(     1.0,     1.0,     1.0,     1.0);
  } elsif($mode eq "ebook") {
    print "DENSE MODE ON\n";
    $chapters_on = 1;
    $chapters_brief = 1;
    $italics_on = 1;
    $spacing = 1;
    $ellipsis = 1;
    $smartquote = 1;
    $emdash = 1;
    $font_size = 12;
    $font = "Palatino Linotype";#Times New Roman";
    $notes_on = 0;
    $bold_chapters = 1;
    $paperw = 6;
    $paperh = 9;
    ($marginl,$marginr,$margint,$marginb) = 
    (     0.5,     0.5,     1.0,     0.5);
  } elsif($mode eq "synopsis") {
    print "SYNOPSIS MODE ON\n";
    $chapters_on = 1;
    $chapters_brief = 1;
    $italics_on = 1;
    $spacing = 1;
    $font_size = 12;
    $font = "Times New Roman";
    $notes_on = 0;
    $bold_chapters = 1;
    ($marginl,$marginr,$margint,$marginb) = 
    (     1.0,     1.0,     1.0,     1.0);
  } else {
    die "Unknown mode";
  }
}

die "bad font" unless (defined($fonts{$font}));

my $fs = 2*$font_size;
my $first_title = 1;
my $wc=0;
my $par=0;
my $header = "";
my $fdr = new FileHandle();
my $fdw = new FileHandle();
my $toc = new FileHandle();
my $infile = $ARGV[0];
my $chapter = 1;
my $titlepg = 0;
die "Not a text file" unless($infile =~ /\.txt$/);

open($fdr,$infile) or die $infile;
open($toc,">toc.txt");
my $ti = "";
my $chwc = "";
my $notes = "";
my @titles = ();
my $tchno = 0;
while(<$fdr>) {
    s/^\s*#.*//;
    if(/<chapter(="([^"]*)")?(\s+sect|)>/) {
        if(defined($2)) {
            my $chname = $2;
            $chname =~ s/’/'/g;
            $chname =~ s/‘/'/g;

            $titles[$tchno] = $chname;
        } else {
            $titles[$tchno] = $tchno + 1;
        }
        $tchno++;
        if($ti ne "") {
            print $toc $ti;
            print $toc "." x (50-length($ti)-length($chwc)),$chwc,"\n";
            $chwc = 0;
        }
        $ti = sprintf "Ch:% 3d",$chapter;
        if(defined($2)) {
            $ti .= ", '$2'";
        }
        print $toc $notes;
        $notes = "";
        $chapter++;
    } elsif(/<font=(["'])(.*)\1>/) {
        addfont($2);
    } elsif(/<scenebrk=(["'])(.*)\1>/) {
        $scenebrk=$2;
    } elsif(/<emdash-on>/) {
        $emdash = 1;
    } elsif(/<problem="([^"]*)">/) {
        $notes .= "    problem: $1\n" if($notes_on);
    } elsif(/<authornote=(['"])(.*)\1>/) {
        ;
    } elsif(/<img=(["'])(.*)\1 mag=(["'])(.*)\3>/) {
        ;
    } elsif(/<note="([^"]*)">/) {
        $notes .= "    note: $1\n" if($notes_on);
    } elsif(/<end>/) {
        last;
    } elsif(/<mode="([^"]*)">/) {
        setmode($1);
    } else {
        s/<[^>]*>//g;
        while(/[\w']+/g) {
            $chwc++;
        }
    }
}
if($ti ne "") {
    print $toc $ti;
    print $toc "." x (50-length($ti)-length($chwc)),$chwc,"\n";
    $chwc = 0;
}
close($toc);
close($fdr);
$chapter = 1;

# Begin
my ($mll,$mlr,$mlt,$mlb)=(
  1440.0*$marginl+.5,
  1440.0*$marginr+.5,
  1400.0*$margint+.5,
  1400.0*$marginb+.5
  );
open($fdr,$infile) or die $infile;
my $outfile = $infile;
$outfile =~ s/\.txt$/.rtf/;
open($fdw,">$outfile") or die $outfile;
print $fdw "{\\rtf1\\ansi\\deff0 {\\fonttbl \n";
for my $fk (keys %fonts) {
    print $fdw "{\\f$fonts{$fk} ${fk};}\n";
}
print $fdw "}\\fs$fs\n";
printf $fdw "\\margl%d\\margr%d\\margt%d\\margb%d\\gutter%d ",$mll,$mlr,$mlt,$mlb,$gutter*1440.0+.5;
printf $fdw "\\paperw%d\\paperh%d",$paperw*1440.0,$paperh*1440.0;
print $fdw "{\\sectd ";
my $init = 1;

my $fdd = new FileHandle;
open($fdd,">dbg1.txt");

while(<$fdr>) {
    if(/^\s*#/) {
        ;
    } elsif(/<title-page=(true|false)>/) {
        #$titlepg = 1;
        #$titlepg = 0 if($1 eq "false");
        print $fdw "\\titlepg ";
    } elsif(/<sect\b([^>]*)>/) {
        endpar();
        print $fdw "\\sect}\n";
        my $opts = $1;
        print $fdw "{\\sectd ";
        if($opts =~ /\bstart\b/) {
          print $fdw "\\pgnrestart\\titlepg ";
        }
        if($opts =~ /\bno-par\b/) {
            $par = 1;
            printf $fdw "{\\pard\\sl%d\\slmult1",240*$spacing;
        }
#    } elsif(/<section>/) {
#        print $fdw " \\sect}{\\sectd\\pgnrestart\\titlepg ";
    } elsif(/<spacing=([\d\.]*)>/) {
        $spacing = $1;
    } elsif(/<set-page-num=(\d+)>/) {
        print $fdw "\\pgnstarts$1\\pgnrestart";
    } elsif(/<(no)?chapter(?:="([^"]*)")?\s*(noskip)?(\s+sect|)>/) {
        my $title = $2;
        $title = accent($title);
        my $noskip = $3;
        endpar();
        if($4 ne "") {
          print $fdw "\\sect}{\\sectd\n";
        } else {
          printf $fdw "{\\pard\\page\\par}\n" unless(defined($noskip));
        }
        if($1 eq "no") {
            ;#$chapter++;
        } else {
            print $fdw "{\\pard \\par}\n" x $chapter_lines unless(defined($noskip));
            print $fdw "\\b " if($bold_chapters);
            print "Chapter $chapter: $title\n";
            my $bkmkid = "a$chapter";
            $titles[$chapter] = $title;
            print $fdw "{\\*\\bkmkstart $bkmkid}{\\*\\bkmkend $bkmkid}\n";
            my $link  = "{\\field{\\*\\fldinst HYPERLINK \\\\l \"[TOC]\"}{\\fldrslt\\ul0 [TOC]}}";
            if($chapters_on) {
                if($chapters_brief) {
                  #print $fdw "{\\pard\\qc {\\tc $title} \\par}\n";
                  print $fdw "{\\pard\\qc $title \\par}\n";
                } else {
                  #print $fdw "{\\pard\\qc Chapter $chapter: {\\tc $title} \\par}\n";
                  print $fdw "{\\pard\\qc Chapter $chapter: $title \\par}\n";
                }
            } else {
                my $chap_str = num2en($chapter);
                $chap_str =~ s/\w+/\L\u$&/g;
                print $fdw "{\\pard\\qc Chapter $chap_str \\par}\n";
            }
            print $fdw "\\b0 " if($bold_chapters);
            $chapter++;
        }
        print $fdw "{\\pard \\par}\n";
        #print $fdw "{\\pard \\par}\n" x 10;
        #printf $fdw "{\\pard\\sb%d \\par}\n",1440*$paperh*0.20;
        #startpar();
    } elsif(/<blank-lines=(\d+)>/) {
        endpar();
        #printf $fdw "{\\pard\\fs24\\sb%d \\par}",1440*$paperh*0.25;
        print $fdw "{\\pard \\par}\n" x ($1-1);
        startpar() unless($par);
    } elsif(/<header="([^"]*)"(?:\s+facing=(on|off))?>/) {
        $header = $1;
        my $facing = $2;
        if($facing eq "on") {
          print $fdw "{\\headerl\\pard\\ql $header\\par}\n";
          print $fdw "{\\facingp\\headerr\\pard\\qr $header\\par}\n";
        } else {
          print $fdw "{\\header\\pard\\qr $header\\par}\n";
        }
    } elsif(/<title="([^"]*)">/) {
        if($first_title) {
            $first_title = 0;
            print $fdw "{\\pard \\par}\n" x $chapter_lines;
        }
        startpar() unless($par);
        print $fdw "\\b " if($bold_chapters);
        print $fdw "\\qc $1";
        print $fdw "\\b0 " if($bold_chapters);
        endpar();
    } elsif(/<quote(.*)>/) {
        endpar();
        my $flags = $1;
        my $ftype = "{\\i";
        if($flags =~/\btype=(\w+)/) {
            if($1 eq "plain") {
                $ftype = "{";
            } elsif($1 eq "italic") {
                $ftype = "{\\i ";
            } elsif($1 eq "underline") {
                $ftype = "{\\ul ";
            } else {
                die "Bad ftype $1";
            }
        }
        if($flags =~ /\bfont=(['"])(.*?)\1/) {
            die "bad font=$2" unless(defined($fonts{$2}));
            $ftype .= "\\f".$fonts{$2};
        }
        my $indent = 720;
        if($flags =~ /\bindent=(\d+(\.\d+)?)/) {
            $indent = int(1440.0*$1);
        }
        #if($1 eq "p") {
        #  print $fdw "{";
        #} elsif($italics_on) {
        #  print $fdw "{\\i ";
        #} else {
        #  print $fdw "{\\ul ";
        #}
        print $fdw $ftype;
        #$main::tighten="\\li720\\ri720\\fi120";
        $main::tighten="\\li${indent}\\ri${indent}\\fi120";
        if($flags =~ /\bcenter\b/) {
            $main::tighten .= "\\qc ";
        }
        startpar();
        endpar();
        startpar();
    } elsif(/<\/quote>/) {
        print $fdw "}";
        $main::tighten="";
        endpar();
        startpar();
    } elsif(/<tocall>/) {
        my $sz = ($paperw-$marginl-$marginr-0.5)*1440;
        $use_toc = 1;
        my $bkmkid = "[TOC]"; 
        print $fdw "{\\*\\bkmkstart $bkmkid}{\\*\\bkmkend $bkmkid}\n";
        for(my $i=0;$i<=$#titles;$i++) {
            my $left = $i;
            my $tc = $i+1; #$titles[$i];
            my $right = "{\\field{\\*\\fldinst PAGEREF a$tc}{\\fldrslt}}";
            $left = $titles[$i];
            my $link  = "{\\field{\\*\\fldinst HYPERLINK \\\\l \"a$tc\"}{\\fldrslt\\ul0 $left}}";
            print $fdw "{\\pard $link \\tqr\\tldot\\tx$sz\\tab\\ql $right \\par}\n";
        }
    } elsif(/<toc=(["'])(\w+)\1 text=\1(.*)\1>/) {
        my $left = $3;
        my $tc = $2;
        my $right = "{\\field{\\*\\fldinst PAGEREF $tc}{\\fldrslt}}";
        my $link  = "{\\field{\\*\\fldinst HYPERLINK \\\\l \"$tc\"}{\\fldrslt\\ul0 $left}}";
        $left = $link;
        #my $wt1 = 0.95;
        #printf $fdw "{\\trowd\\cellx%d\\cellx%d\\pard\\intbl %s\\cell\\pard\\intbl\\qr %s\\cell\\row}\n",$wt1*1440.0*($paperw-$marginl-$marginr),1440.0*($paperw-$marginl-$marginr),$left,$right;
        #print $fdw "\\pard\\intbl\\ql{$left\\tqr\\tldot\\tx9200\\tab\\ql{.}{\\field{\\*\\fldinst PAGEREF $tc}}}\\cell\\row\n";
        #print $fdw "{\\intbl\\cell\\pard $left\\tqr\\tldot\\tx9200\\tab\\cell$right \\row}\n";
        my $sz = ($paperw-$marginl-$marginr-1.0)*1440;
        #\pard\intbl\ql {\field{\*\fldinst HYPERLINK \\l "page2"} {\fldrslt\ul0 Link to anchor #page2}}\cell\pard\intbl\qr {\field{\*\fldinst PAGEREF page2}}\cell\row
        print $fdw "{\\pard $left \\tqr\\tldot\\tx$sz\\tab\\ql $right \\par}\n";
    } elsif(/<bookmark=(["'])(\w+)\1>/) {
        my $bkmkid = $2;
        print $fdw "{\\*\\bkmkstart $bkmkid}{\\*\\bkmkend $bkmkid}\n";
    } elsif(/<spacing=(\d+)>/) {
        $spacing = $1*1;
    } elsif(/<end>/) {
        last;
    } elsif(/<authornote=(['"])(.*)\1>/) {
        ;
    } elsif(/<img=(["'])(.*)\1 mag=(["'])(.*)\3>/) {
        my $imgfile = $2;
        my $mag = $4;
        my $fdi = new FileHandle;
        open($fdi,"file '$imgfile'|");
        my $out = <$fdi>;
        die "die out='$out'" unless($out =~ /,\s*(\d+)\s*x\s*(\d+)\s*,/);
        my ($width,$height)=($1,$2);
        $mag = 14.4 unless(defined($mag));
        my ($goalw,$goalh)=(int($mag*$width),int($mag*$height));
        print $fdw '{\pard\qc{\shppict{\pict\picw',$width,'\pich',$height,'\picwgoal',$goalw,'\pichgoal',$goalh,'\pngblp ';
        open($fdi,$imgfile) or die $imgfile;
        binmode($fdi);
        my $buf;
        while(read($fdi,$buf,64)) {
          while($buf =~ /./gs) {
            print $fdw sprintf("%02x",ord($&));
          }
          print $fdw "\n";
        }
        print $fdw "}}\\par}\n";
    } elsif(/<(note|problem)="([^"]*)">/) {
        print $fdw "{\\rtlch \\ltrch\\loch {\\*\\atnid }\\chatn{\\*\\annotation{\\*\\atnref 0}$1}}\n"
            if($notes_on);
    } elsif(/<scene.*>/) {
        endpar();
        if($center_scene_brk) {
          print $fdw "{\\pard \\par}{\\pard\\qc ${scenebrk} \\par}\n";
        } else {
          startpar();
          print $fdw "#";
          endpar();
        }
        $par = 0;
    } elsif(/<heading="([^"]*)">/) {
        print $fdw "{\\pard\\qc $1 \\par}\n{\\pard \\par}\n";
    } elsif(/<line="([^"]*)"( +right="([^"]*)")?>/) {
        my $left = $1;
        my $right = $3;
        if(defined($right)) {
          printf $fdw "{\\trowd\\cellx%d\\cellx%d\\pard\\intbl %s\\cell\\pard\\intbl\\qr %s\\cell\\row}\n",0.5*1440.0*($paperw-$marginl-$marginr),1440.0*($paperw-$marginl-$marginr),$left,$right;
        } else {
          printf $fdw "{\\trowd\\cellx%d\\pard\\intbl %s\\cell\\row}\n",1440.0*($paperw-$marginl-$marginr)+1440.0*($paperw-$marginl-$marginr),$left;
          #printf $fdw "{\\trowd\\cellx%d\\cellx%d\\pard\\intbl %s\\cell\\row}\n",1440.0*($paperw-2.4*$margins),1440.0*($paperw-2.5*$margins),$left;
        }
    #} elsif(/<.*>/) {
    #    print "Undefined control $&\n";
    } elsif(/<mode="[^"]+">/) {
      ;
    } elsif(/<scene-brk>/) {
      ;
    } elsif(/<emdash-on>/) {
      ;
    } elsif(/<cover=/) {
      ;
    } elsif(/<author=/) {
      ;
    } elsif(/<bookid=/) {
      ;
    } elsif(/<geometry=/) {
      ;
    } elsif(/<font=.*>/) {
      ;
    } elsif(/^\s*<[\w-]+(="[^"]*")?>\s*$/) {
        die "undefined control ".$&;
    } elsif(/^\s*$/) {
        if($par) {
            endpar();
            #startpar();
        }
    } else {
        if($init) {
          print $fdw "\\titlepg " if($titlepg);
          $init = 0;
        }
        startpar() unless($par);
        my $line = $_;
        my $buf = accent($_);
        $buf =~ s/<[^>]*>//g;
        while($buf =~ /(\\?)[A-Za-z_'-]+/g) {
          next if($1 eq "\\");
          $wc++;
        }
        print $fdd $buf;
        startpar() unless($par);
        if($italics_on) {
          s/<i>/\\i /g;
          s/<\/i>/\\i0 /g;
        } else {
          s/<i>/\\ul /g;
          s/<\/i>/\\ul0 /g;
        }
        s(<a href='([^']*)'>([^<]*)</a>)({\\field{\\*\\fldinst HYPERLINK \\\\l \"$1\"}{\\fldrslt $2}}); # yyy
        s/<c>/\\qc /g;
        s/<b>/\\b /g;
        s/<trade>/{\\'99}/g;
        s/<copyright>/{\\'a9}/g;
        s/<\/b>/\\b0 /g;
        $_ = accent($_);
        #s/--/{\\u8212}/g if($emdash);
        s/--/{\\emdash}/g if($emdash);
        #s/\.\.\./{\\u8212}/g if($ellipsis);
        #s/\.\.\./{\\ellipsis}/g if($ellipsis);
        s/\.\.\./{\\u8230\\'81}/g if($ellipsis);
        print $fdw $_;
    }
}
close($fdd);
endpar();

my $wcn = $wc - 7416;

print $fdw "\\sect}\n";
print $fdw "}\n";
print "Word Count=$wc\n";
my @d = localtime();
if ($d[4] == 10) {
    my $goal = 50e3;
    for my $count ((30,29,28)) {
        my $wday = $goal/$count;
        my $mwcn = int($wday*$d[3]);
        $wday = int($wday);
        my $dwcn = $mwcn - $wcn;
        print "Nano: Word Count=$wcn + $dwcn = $mwcn, w/day=$wday for $count days\n";
    }
    my $rem = $goal - $wcn;
    print("Nano: Remaining: $rem\n");
}
print "Chapters on: $chapters_on\n";
print "Notes on: $notes_on\n";
print "Italics on: $italics_on\n";
print "Font: $font\n";
sub startpar {
    endpar() if($par);
    $par = 1;
    #my $ind = sprintf("%d",$margins*720.0+0.5);
    my $ind = sprintf("%d",$indent*1440.0+0.5);
    printf $fdw "{\\pard\\fi$ind\\sl%d\\slmult1$main::tighten",240*$spacing;
}
sub endpar {
    print $fdw "\\par}\n" if($par);
    $par = 0;
}
sub count {
  $wc++;
  return $wc;
}

sub altquote
{
  my $arr = shift;
  if($$arr == 0) {
    $$arr = 1;
    return "{\\ldblquote}";
  } else {
    $$arr = 0;
    return "{\\rdblquote}";
  }
}
# https://www.safaribooksonline.com/library/view/rtf-pocket-guide/9781449302047/ch04.html
sub accent {
  my $txt = shift;
  my $count = 0;
  $txt =~ s/\\+'e/\\u233\\'e9/g;
  $txt =~ s/<'e>/\\u233\\'e9/g;
  $txt =~ s/<'a>/\\u225\\'e1/g;
  $txt =~ s/<'o>/\\u243\\'f3/g;
  $txt =~ s/<'i>/\\u237\\'ed/g;
  $txt =~ s/<~n>/\\u241\\'f1/g;
  $txt =~ s/<~a>/\\u227\\'e3/g;
  $txt =~ s/<'u>/\\u250\\'fa/g;
  $txt =~ s/<:o>/\\u246\\'f6/g;
  $txt =~ s/<bullet>/{\\bullet}/g;
  $txt =~ s/\.\.\.+/{\\u8230\\'81}/g if($ellipsis);
  #$txt =~ s/\.\.\.+/{\\ellipsis}/g if($ellipsis);
  $txt =~ s/``/{\\ldblquote}/g;
  $txt =~ s/''/{\\rdblquote}/g;
  $txt =~ s/\\?"/altquote(\$count)/ge if($smartquote);
  $txt =~ s/--/{\\emdash}/g if($emdash);
  $txt =~ s/ō/\\u333\\'3f/g;
  $txt =~ s/ū/\\u363\\'3f/g;
  $txt =~ s/ā/\\u257\\'3f/g;
  $txt =~ s/ñ/\\u241\\'f1/g;
  $txt =~ s/é/\\u233\\'e9/g;
  $txt =~ s/ó/\\u243\\'f3/g;
  $txt =~ s/¿/\\u191\\'bf/g;

  $txt =~ s/’/'/g;
  $txt =~ s/‘/'/g;
  $txt =~ s/…/.../g;
  #my $all = "";
  #for(my $i=150;$i<300;$i++) {
  #  $all .= sprintf(" \\u%d\\'%x (%d)",$i,$i,$i);
  #}
  #$txt =~ s/<-all->/all: $all/g;
  return $txt
}
