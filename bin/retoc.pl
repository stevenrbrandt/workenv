#!/usr/bin/perl
use strict;
use FileHandle;
my $fd = new FileHandle;
my $sum = 0;
open($fd,"toc.txt");
while(<$fd>) {
  chomp;
  if(/(\d+)$/) {
    $sum += 1*$1;
  }
}
close($fd);

my $sum2=0;
open($fd,"toc.txt");
while(my $line=<$fd>) {
  next if($line =~ /(problem|note):/);
  chomp($line);
  if($line=~/(\d+)$/) {
    $sum2 += 1*$1;
  }
  printf("%s %6.0f %10.0f\n",$line,100.0*$sum2/$sum,$sum2);
}
close($fd);
print "\nSUM=$sum\n";
