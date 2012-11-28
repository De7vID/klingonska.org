#!/usr/bin/perl
#
# lexicon.cgi - online search engine for zrajm's klingon database

###############################################################################
##                                                                           ##
##  Initializations                                                          ##
##                                                                           ##
###############################################################################

use warnings;
use strict;
use utf8;
use CGI qw(:standard);
use Encode 'decode';
binmode(STDIN,  ":encoding(utf8)");
binmode(STDOUT, ":encoding(utf8)");

# output content-type header
# (when used as SSI or loaded explicitly by
# browser, but not when called by other script)
if (not $ENV{X_CGI}) {                         # if not suppressed
    print header(-charset=>'utf-8');           # Content-type header
    $ENV{X_CGI} = "perl";                      #   and suppress it from now on
}                                              #

# language (en=english/sv=swedish)
my $lang = lc ($ENV{LANG} || $ENV{X_LANG});    # get language
$lang = $lang eq "sve" ? "sv" :                #
        $lang eq "eng" ? "en" : $lang;         #
$lang = "en" unless $lang =~ /^(en|sv)$/;      #

our %postprocess = (
    file => sub {
        my ($value) = @_;
        my $i = 0;
        return map {
            my $string = ($i++ ? "\n      <br>" : "") . "<a href=\"../canon/$_\">$_</a>";
            $string .= " (<strong>NOTE:</strong> <abbr title=\"The Klingon " .
                "Dictionary\">TKD</abbr> required to view this file.)"
                    if defined($_) and m#-(tkd|tkw|kgt)\.txt#;
            $string;
        } split(m#;\s*#, $value);
    },
);

our %field = (
    tlh  => "Klingon word",
    warn => "Warning",
    pos  => "Part-of-speech",
    sv   => "Swedish translation",
    en   => "English translation",
    desc => "Description",
    def  => "Defining source",
    ref  => "Referring source",
    com  => "Comment",
    pun  => "Pun",
    see  => "See also",
    tag  => "Tags",
    data => "Data",
    id   => "Permanent Entry ID",
    file => "Transcript",
    meta => "Metadata",
);

our @tips = (
    'Hover over a field in search results to see field description.',
    'Use a search prefix (e.g. <a href="?q=tag:klcp1"><b>tag:klcp1</b></a>) ' .
        'to search only a given field (here: <b>tag:</b>).',
    'Use <a href="?q=def:HQ10:4"><b>def:HQ10:4</b></a> to lists all words ' .
        'first occurring in <i><a href="../canon/2001-12-holqed-10-4.txt">' .
        '<b lang=tlh>HolQeD</b> issue 10:4</a>.</i>',
    'Prefixes: <b>tlh:</b> = Klingon, <b>en:</b> = English, <b>sv:</b> = ' .
        'Swedish, <b>pos:</b> = part-of-speech.',
    'Prefixes: <b>com:</b> = comment, <b>def:</b> = defining source, ' .
        '<b>ref:</b> = referring source.',
    'Use <a href="?q=tlh:*chuq"><b>tlh:*chuq</b></a> to finds all Klingon ' .
        'words ending in <b>chuq.</b>',
    'Use <a href="?q=tag:klcp1"><b>tag:klcp1</b></a> to find all ' .
        '<a href="../klcp.html#_6">first level words</a> from the<br>' .
        '<a href="../klcp.html"><i>Klingon Language Certification Program' .
        '</i></a>.',
    'Use <a href="?q=def:kgt"><b>def:kgt</b></a> to find all words first ' .
        'occurring in <i><a href="../canon/1997-11-01-kgt.txt">KGT</a>.</i>',
    'Put <b>tlh:</b> before a word to search only Klingon fields for it.',
    'Put <b>en:</b> before a word to search only English fields for it.',
    'Put <b>sv:</b> before a word to search only Swedish fields for it.',
    'Use <b>pos:v</b> to search for <i>verbs</i> (see <i>' .
        '<a href="intro.html#pos">Introduction</a></i> for other word ' .
        'types).</i>',
    'Use <a href="?q=pos:ns2"><b>pos:ns2</b></a> to find <i>noun suffixes '.
        'type 2</i> (also try numbers <i>1&#8211;5</i>).',
    'Use <a href="?q=pos:vs1"><b>pos:vs1</b></a> to find <i>verb suffixes ' .
        'type 1</i> (also try letter <i>r,</i> and numbers <i>1&#8211;9</i>).',
    'Use <a href="?q=pos:vsr"><b>pos:vsr</b></a> or <a href="?q=pos:rover">' .
        '<b>pos:rover</b></a> to search for <i>verb suffix rovers.</i>',
    'Use <b>*</b> to mean any sequence of letters when searching.',
    'Use quotes (<b>"…"</b>) to search for several words after each other.',
    'With multiple search words, all are needed for a match (e.g. ' .
        '<a href="?q=en:battle pos:v"><b>en:battle pos:v</b></a>).',
    'Search is never case sensetive, except with <b>tlh:</b> prefix.',
);


################################################################################
###                                                                           ##
###  Subroutines                                                              ##
###                                                                           ##
################################################################################

sub read_dictionary {
    my ($file) = @_;
    open(my $fh, "<:encoding(utf8)", $file) or
        die "cannot open dictionary file '$file'";
    # skip file header
    while (<$fh>) {
        last if $_ eq "== start-of-data ==\n";
    }
    # read dictionary
    my @buf = ();
    while (<$fh>) {
        chomp();
        last if $_ =~ /^== end-of-data ==$/;   # terminate at file footer
        next if /^===\s/;                      # skip section delimiters
        if (/^$/) {                            # beginning of new post
            push(@buf, "");
            next if /^$/;                      #   skip to next line in file
        }                                      #   if this one is empty now
        # indented line, or new field
        if (s/^\s+//) {                        # if line begins with white space
            $buf[$#buf] .= " " . $_;           #   join it to buffer's last line
        } else {                               # otherwise
            $buf[$#buf] .= "\n" . $_;          #   add new line to buffer
        }
    }
    close($fh);
    return map { s/[<>«»]//g; $_ } @buf;
}


# Usage: @REGEX = split_query($QUERY);
#
# Takes a QUERY and splits it into phrases (a phrase is a word or a double
# quoted string).
#
# Returs a list of regexes for matching that query. A phrase may start with a
# field name (e.g. 'tlh:') to match only that field. If a phrase is quoted then
# the field name must occur before the quotes, i.e. 'tlh:"hej"' is interpreted
# the same as 'tlh:hej' (search field "tlh" for string "hej"), while
# '"tlh:hej"' is interpreted literally (search any field for string "tlh:hej").
#
# TODO: implement negative queries?
sub split_query {
    my ($query) = @_;
    # split query into words and quoted strings
    my @subquery = $query =~ m/([^\s"]+(?:"[^"]+"?)?|"[^"]+"?)/g;
    my %pos = (
        v    => "verb",
        n    => "noun",
        name => "name",
        adv  => "adverbial",
        conj => "conjunction",
        excl => "exclamation",
        num  => "numeral",
        pro  => "pronoun",
        ques => "question word",
        ns1  => "noun suffix type 1",
        ns2  => "noun suffix type 2",
        ns3  => "noun suffix type 3",
        ns4  => "noun suffix type 4",
        ns5  => "noun suffix type 5",
        vp   => "verb prefix",
        vsr  => "verb suffix type rover",
        vs1  => "verb suffix type 1",
        vs2  => "verb suffix type 2",
        vs3  => "verb suffix type 3",
        vs4  => "verb suffix type 4",
        vs5  => "verb suffix type 5",
        vs6  => "verb suffix type 6",
        vs7  => "verb suffix type 7",
        vs8  => "verb suffix type 8",
        vs9  => "verb suffix type 9",
        number => "numeral",
        rover  => "verb suffix type rover",
    );
    # turn subqueries into regexes
    my $w = "[\\w']";                             # word character class
    return map {
        # split subquery into field name & search phrase
        my ($field, $phrase) = /^ (?:([^":]*):)? "?(.*?)"? $/x;
        # quote metacharacters + "any field" if field was empty
        $field  = defined($field) ? quotemeta(lc($field)) : "[^:]*";
        $phrase = quotemeta($phrase);
        # all fields are case insensetive, except "tlh"
        my $lcphrase = lc $phrase;
        if ($field eq "pos" and exists($pos{$lcphrase})) {
            qr/^($field:)\t($pos{$lcphrase})$/m;
        } elsif ($field eq "id") {
            my %chr = (0 => 'o', O => 'o', I => '1', l => '1');
            for ($phrase) { s/([0OIl])/$chr{$1}/g; s/\\[*]/.*/g; }
            qr/^($field:)\t($phrase)$/m;  # case sensetive
        } else {
            $field = "tag" if $field eq "cat";
            for ($phrase) { s/\\\*/$w*/g; s/\s+/\\s+/g; } # replace '*' and ' '
            if ($field eq "tlh") {
                qr/^($field:.*)(?<!$w)($phrase)(?!$w)/m;  # case sensetive
            } else {
                qr/^($field:.*)(?<!$w)($phrase)(?!$w)/im; # case insensetive
            }
        }
    } @subquery;
}

sub html_no_match {
    my ($query) = @_;
return <<"EOF";
<p>Your search &ndash; <b>$query</b> &ndash; did not match any
dictionary entries.</p>

<p>Suggestions:</p>

<p>
  <ul>
    <li>Make sure all words are spelled correctly.</li>
    <li>Try different keywords.</li>
    <li>Try more general keywords.</li>
  </ul>
</p>

EOF
}

sub html_empty_page {
return <<"EOF";

<p>The book has a Klingon&ndash;English, and an English&ndash;Klingon side. The
wordlists are automatically generated from <a href="dict.zdb">a simple text
based database</a>, which is human readable and easy to update. The database
has been continuously updated and improved since it was created in late
<time>1997</time>.</p>

<table class="noborder layout">
  <tr>
    <th colspan=2>Search Expressions</th>
  </tr>
  <tr>
    <td class=center><b>"</b>…<b>"</b>&nbsp;</td>
    <td>search for a phrase (containing more than one word)</td>
  </tr>
  <tr>
    <td class=center><b>*</b>&nbsp;</td>
    <td>matches any alphabetical character</td>
  </tr>
  <tr>
    <td class=center><b>tlh:</b>…&nbsp;</td>
    <td>search Klingon words <i>(case sensetive)</i></td>
  </tr>
  <tr>
    <td class=center><b>en:</b>…&nbsp;</td>
    <td>search English translations</td>
  </tr>
  <tr>
    <td class=center><b>sv:</b>…&nbsp;</td>
    <td>search Swedish translations</td>
  </tr>
  <tr>
    <td class=center><b>pos:</b>…&nbsp;</td>
    <td>search part-of-speech field<br>(use abbrev
      from <i><a href="intro.html">Introduction</a></i>, <i>ns#,</i> <i>vs#</i>
      or free text)</td>
  </tr>
  <tr>
    <td class=center><b>def:</b>…&nbsp;</td>
    <td>search defining sources</td>
  </tr>
  <tr>
    <td class=center><b>ref:</b>…&nbsp;</td>
    <td>search referring sources</td>
  </tr>
</table>

<p>Case <em>only</em> matters when you’re using the search prefix <b>tlh:</b>,
otherwise all searches are case insensetive.</p>

EOF
}

sub html_head {
return <<"EOF";
<!doctype html>
<!--[if lt IE 7]> <html class="no-js lt-ie9 lt-ie8 lt-ie7" lang=en> <![endif]-->
<!--[if IE 7]>    <html class="no-js lt-ie9 lt-ie8" lang=en> <![endif]-->
<!--[if IE 8]>    <html class="no-js lt-ie9" lang=en> <![endif]-->
<!--[if gt IE 8]><!--> <html class="no-js" lang=en> <!--<![endif]-->
<head>
  <meta charset="UTF-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
  <title>Klingon Pocket Dictionary &ndash; Klingonska Akademien</title>
  <meta name=viewport content="width=device-width">
  <link rel=stylesheet href="../includes/base.css">
  <link rel=stylesheet href="../includes/dict.css">
  <link rel=stylesheet href="../includes/pagetabs.css">
  <link rel=icon href="/favicon.ico">
  <link rel=canonical href="http://klingonska.org/dict/">
  <script src="../includes/modernizr-2.5.3.js"></script>
  <style><!--
    td, th { vertical-align: text-top; }
    th {
      font-weight: normal;
      white-space: nowrap;
      text-align: left;
    }
    mark { background-color: #bbb; font-weight: inherit; font-style: inherit; }
  --></style>
</head>
<body lang=en itemscope itemtype="http://schema.org/WebPage">

<header role=banner class=tabbed>
  <!-- begin:status -->
  <ul>
    <li>
      <nav itemprop=breadcrumb role=navigation>
        <a href="http://klingonska.org/">Home</a> &gt;
        <a href="http://klingonska.org/dict/">Klingon Pocket Dictionary</a>
      </nav>
    </li>
    <li>
      Updated <time pubdate datetime="2012-11-10T00:50">November 10, 2012</time>
    </li>
  </ul>
  <!-- end:status -->
  <div>
    <a href="../">
      <table id=logotitle>
        <td>
          <span class=crop>
            <img height=200 width=200 src="../pic/ka-logo.svg" alt="Klingonska Akademien">
          </span>
        </td>
        <td>
          <h1>Klingonska<span id=logospace>&nbsp;</span>Akademien</h1>
        </td>
      </table>
    </a>
    <nav class=pagetabs>
      <ul role=navigation>
        <li><a href="about.html">About</a></li>
        <li><a href="intro.html">Introduction</a></li>
        <li class=selected>Lexicon</li>
        <li><a href="suffix.html">Suffix Guide</a></li>
        <li><a href="tables.html">Reference Tables</a></li>
      </ul>
    </nav>
  </div>
</header>

<article role=main itemprop=mainContentOfPage style="padding-top:1px">
<h1>Klingon Pocket Dictionary</h1>

<aside class=note>Some info + searchable version of the pocket dictionary database.</aside>

<section>
EOF
}

sub html_form {
    my ($query) = (@_, "");
    my $focus_attr = $query ? '' : ' autofocus';
    $query = escapeHTML($query);
    (my $script_name = $0) =~ s#^.*/##;
    my $tips = $tips[int(rand(@tips))];
    return <<"EOF";

<table class="noborder layout">
  <tr>
    <td class=center>
      <form method=get action="">
        <input$focus_attr tabindex=1 name=q value="$query" size=35
          placeholder="Search terms…"><input type=submit value=Search>
      </form>
    </td>
  </tr>
  <tr>
    <td class=center><small>$tips</small></td>
  </tr>
</table>

EOF
}

sub html_foot {
    return <<'EOF';
</section>
</article>

<footer role=contentinfo>
  <p class=copyright>&copy;<time itemprop=copyrightYear>1998</time>&ndash;<time>2012</time> by
    <a href="mailto:zrajm@klingonska.org" rel=author itemprop=author>Zrajm C Akfohg</a>,
    <a href="http://klingonska.org/" itemprop=sourceOrganization>Klingonska Akademien</a>, Uppsala
  </p>
  <p class=validator>
    Validate:
    <a href="http://validator.w3.org/check?uri=http://klingonska.org/">HTML5</a>,
    <a href="http://jigsaw.w3.org/css-validator/validator?uri=http://klingonska.org/&amp;profile=css3">CSS3</a>,
    <a href="http://validator.w3.org/checklink?uri=http://klingonska.org/">links</a>.
    License:
    <a href="http://creativecommons.org/licenses/by-sa/3.0/" rel=license>CC BY&ndash;SA</a>.&nbsp;
  </p>
</footer>
<script>var _gaq=[['_setAccount','UA-5434527-2'],['_trackPageview']];
(function(d,t){var g=d.createElement(t),s=d.getElementsByTagName(t)[0];
g.src=('https:'==location.protocol?'//ssl':'//www')+'.google-analytics.com/ga.js';
s.parentNode.insertBefore(g,s)}(document,'script'))</script>
<script src="../includes/titlewrap.js"></script>
</body>
</html>
EOF
}


###############################################################################
##                                                                           ##
##  Main Program                                                             ##
##                                                                           ##
###############################################################################

# no query: display empty search form & exit
if (not param("q")) {
    print
        html_head() .
        html_form() .
        html_empty_page() .
        html_foot();
    exit 0;
}

# read query from HTML form value
my $query = param("q");             # read form "q" value
$query = "" unless defined($query); # make sure it's never undef
$query = decode("UTF-8", $query);   # UTF-8 decode it

print html_head() . html_form($query);
{
    # make list of page content
    my @regex   = split_query($query);
    my @output  = ();
    my $matches = 0;
  WORD: foreach (read_dictionary("dict.zdb")) {
        # highlight matching words
        foreach my $regex (@regex) {
            s#$regex#$1<mark>$2</mark>#m or next WORD;
        }
        push @output, '  <tr><td colspan=2>&nbsp;</td></tr>' . "\n"
            if $matches > 0;
        $matches ++;
        # presentation
        s#([{}])# $1 eq "{" ? "<b lang=\"tlh\">" : "</b>" #ge;  # boldify
        s#~(.*?)~#<i>$1</i>#g;      # apply italics
        s#(.*)¿\?(.*)#$1$2 (uncertain translation)#g;
        s/^\n//;
        foreach (split(/\n/, $_)) {
            my ($field, @content) = split(/:/, $_, 2);
            s/^\s+//, s/\s+$// foreach @content;
            if (exists($postprocess{$field})) {
                @content = &{$postprocess{$field}}(@content);
                next unless @content;
            }
            push @output,
                "  <tr title=\"" .
                    (exists $field{$field} ? $field{$field} : ucfirst $field) .
                    " (search prefix “$field:”)\">\n",
                "    <th class=right><span class=light>$field:</span></th>\n",
                "    <td>@content</td>\n",
                "  </tr>";
        }
    }
    # output page
    if ($matches == 0) {
        print html_no_match($query);
    } else {
        print '<table class="noborder layout">' . "\n";
        print '  <tr><td colspan=2>' . $matches . ' match' . ($matches == 1 ? "" : "es") . ".</td></tr>\n";
        print '  <tr><td colspan=2>&nbsp;</td></tr>' . "\n";
        print @output;
        print "</table>\n\n";
    }
}
print html_foot();

#[eof]
